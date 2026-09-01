"""Shared CUDA source helpers for the CuPy TMz kernel provider.

This module keeps raw CUDA string templates and small source-generation helpers
separate from the provider's cache/dispatch logic. The provider remains
responsible for precision policy and kernel registry behavior, while this
module owns the source fragments used to build those kernels.
"""

from __future__ import annotations

import re


def sanitize_identifier(name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in name)


def complex_pair_threads(relation: str, num_quadrature: int) -> int:
    # Complex double kernels are register and shared-memory heavy. For the
    # medium-sized regular rules used in the 2D Helmholtz assembly, 64 threads
    # tends to give better occupancy than the previous fixed 128-thread launch.
    if int(num_quadrature) <= 160:
        return 64
    return 128


def complex_hankel_device_helpers_with_params(
    threshold: float,
    asymptotic_terms: int,
    series_terms: int = 48,
    series_tol: float = 1.0e-16,
) -> str:
    return (
        COMPLEX_HANKEL_ORDERS01_DEVICE_HELPERS
        .replace(
            "if (magnitude < 15.0) {",
            f"if (magnitude < {float(threshold):.1f}) {{",
        )
        .replace(
            "for (int k = 1; k < 10; ++k) {",
            f"for (int k = 1; k < {int(asymptotic_terms)}; ++k) {{",
        )
        .replace(
            "for (int m = 1; m < 48; ++m) {",
            f"for (int m = 1; m < {int(series_terms)}; ++m) {{",
        )
        .replace(
            "for (int m = 0; m < 48; ++m) {",
            f"for (int m = 0; m < {int(series_terms)}; ++m) {{",
        )
        .replace(
            "if (complex_abs(term0) < 1.0e-16 * fmax(1.0, complex_abs(j0))) {",
            f"if (complex_abs(term0) < {float(series_tol):.1e} * fmax(1.0, complex_abs(j0))) {{",
        )
        .replace(
            "if (complex_abs(term1) < 1.0e-16 * fmax(1.0, complex_abs(j1))) {",
            f"if (complex_abs(term1) < {float(series_tol):.1e} * fmax(1.0, complex_abs(j1))) {{",
        )
    )


COMPLEX_HANKEL_ORDERS01_DEVICE_HELPERS = r"""
__device__ inline double complex_abs(const complex<double>& z) {
    return hypot(z.real(), z.imag());
}

__device__ inline void hankel_series_orders01(
    const complex<double>& z,
    complex<double>& h0,
    complex<double>& h1)
{
    const double pi = 3.141592653589793238462643383279502884;
    const double gamma = 0.577215664901532860606512090082402431;
    const complex<double> imag_unit(0.0, 1.0);
    const complex<double> t = 0.25 * z * z;

    complex<double> j0(1.0, 0.0);
    complex<double> term0(1.0, 0.0);
    complex<double> s0(0.0, 0.0);
    double harmonic = 0.0;
    for (int m = 1; m < 48; ++m) {
        const double denom = static_cast<double>(m) * static_cast<double>(m);
        term0 *= (-t) / denom;
        harmonic += 1.0 / static_cast<double>(m);
        j0 += term0;
        s0 += (-harmonic) * term0;
        if (complex_abs(term0) < 1.0e-16 * fmax(1.0, complex_abs(j0))) {
            break;
        }
    }

    const complex<double> log_term = log(0.5 * z) + gamma;
    const complex<double> y0 = (2.0 / pi) * (log_term * j0 + s0);
    h0 = j0 + imag_unit * y0;

    complex<double> j1(0.0, 0.0);
    complex<double> s1(0.0, 0.0);
    complex<double> term1 = 0.5 * z;
    double harmonic_m = 0.0;
    for (int m = 0; m < 48; ++m) {
        if (m > 0) {
            const double denom = static_cast<double>(m) * static_cast<double>(m + 1);
            term1 *= (-t) / denom;
            harmonic_m += 1.0 / static_cast<double>(m);
        }
        const double harmonic_mp1 = harmonic_m + 1.0 / static_cast<double>(m + 1);
        j1 += term1;
        s1 += (harmonic_m + harmonic_mp1) * term1;
        if (complex_abs(term1) < 1.0e-16 * fmax(1.0, complex_abs(j1))) {
            break;
        }
    }

    const complex<double> y1 =
        (-2.0 / pi) / z
        + (2.0 / pi) * log_term * j1
        - (1.0 / pi) * s1;
    h1 = j1 + imag_unit * y1;
}

__device__ inline complex<double> hankel_asymptotic(const complex<double>& z, const int order) {
    const double pi = 3.141592653589793238462643383279502884;
    const complex<double> imag_unit(0.0, 1.0);
    const double mu = 4.0 * static_cast<double>(order * order);
    const complex<double> prefactor =
        sqrt(2.0 / (pi * z))
        * exp(imag_unit * (z - 0.5 * static_cast<double>(order) * pi - 0.25 * pi));

    complex<double> series(1.0, 0.0);
    complex<double> inv_z = 1.0 / z;
    complex<double> inv_z_power(1.0, 0.0);
    complex<double> imag_power(1.0, 0.0);
    double coeff = 1.0;
    for (int k = 1; k < 10; ++k) {
        const double odd = static_cast<double>(2 * k - 1);
        coeff *= (mu - odd * odd) / (static_cast<double>(k) * 8.0);
        inv_z_power *= inv_z;
        imag_power *= imag_unit;
        series += imag_power * coeff * inv_z_power;
    }
    return prefactor * series;
}

__device__ inline void hankel_orders01_complex(
    const complex<double>& z,
    complex<double>& h0,
    complex<double>& h1)
{
    const double magnitude = complex_abs(z);
    if (magnitude < 15.0) {
        hankel_series_orders01(z, h0, h1);
        return;
    }
    h0 = hankel_asymptotic(z, 0);
    h1 = hankel_asymptotic(z, 1);
}
"""


COMPLEX_REDUCTION_DEVICE_HELPERS = r"""
__device__ inline complex<double> warp_reduce_complex_sum(complex<double> value) {
    const unsigned int mask = 0xffffffffu;
    for (int offset = warpSize / 2; offset > 0; offset >>= 1) {
        value += complex<double>(
            __shfl_down_sync(mask, value.real(), offset),
            __shfl_down_sync(mask, value.imag(), offset)
        );
    }
    return value;
}

template <int NumWarps>
__device__ inline complex<double> block_reduce_complex_sum(
    complex<double> value,
    complex<double>* shared)
{
    const int lane = threadIdx.x & (warpSize - 1);
    const int warp = threadIdx.x / warpSize;
    value = warp_reduce_complex_sum(value);
    if (lane == 0) {
        shared[warp] = value;
    }
    __syncthreads();
    if (warp == 0) {
        value = lane < NumWarps ? shared[lane] : complex<double>(0.0, 0.0);
        value = warp_reduce_complex_sum(value);
    }
    return value;
}
"""


COMPLEX64_REGULAR_HANKEL_ORDERS01_DEVICE_HELPERS = r"""
__device__ inline float complex_abs_f(const complex<float>& z) {
    return hypotf(z.real(), z.imag());
}

__device__ inline void hankel_series_orders01(
    const complex<float>& z,
    complex<float>& h0,
    complex<float>& h1)
{
    const float pi = 3.14159265358979323846f;
    const float gamma = 0.57721566490153286061f;
    const complex<float> imag_unit(0.0f, 1.0f);
    const complex<float> t = 0.25f * z * z;

    complex<float> j0(1.0f, 0.0f);
    complex<float> term0(1.0f, 0.0f);
    complex<float> s0(0.0f, 0.0f);
    float harmonic = 0.0f;
    for (int m = 1; m < 20; ++m) {
        const float m_float = static_cast<float>(m);
        const float denom = m_float * m_float;
        term0 *= (-t) / denom;
        harmonic += 1.0f / m_float;
        j0 += term0;
        s0 += (-harmonic) * term0;
        if (complex_abs_f(term0) < 2.5e-6f * fmaxf(1.0f, complex_abs_f(j0))) {
            break;
        }
    }

    const complex<float> log_term = log(0.5f * z) + gamma;
    const complex<float> y0 = (2.0f / pi) * (log_term * j0 + s0);
    h0 = j0 + imag_unit * y0;

    complex<float> j1(0.0f, 0.0f);
    complex<float> s1(0.0f, 0.0f);
    complex<float> term1 = 0.5f * z;
    float harmonic_m = 0.0f;
    for (int m = 0; m < 20; ++m) {
        if (m > 0) {
            const float m_float = static_cast<float>(m);
            const float denom = m_float * (m_float + 1.0f);
            term1 *= (-t) / denom;
            harmonic_m += 1.0f / m_float;
        }
        const float harmonic_mp1 = harmonic_m + 1.0f / static_cast<float>(m + 1);
        j1 += term1;
        s1 += (harmonic_m + harmonic_mp1) * term1;
        if (complex_abs_f(term1) < 2.5e-6f * fmaxf(1.0f, complex_abs_f(j1))) {
            break;
        }
    }

    const complex<float> y1 =
        (-2.0f / pi) / z
        + (2.0f / pi) * log_term * j1
        - (1.0f / pi) * s1;
    h1 = j1 + imag_unit * y1;
}

__device__ inline complex<float> hankel_asymptotic(const complex<float>& z, const int order) {
    const float pi = 3.14159265358979323846f;
    const complex<float> imag_unit(0.0f, 1.0f);
    const float mu = 4.0f * static_cast<float>(order * order);
    const complex<float> prefactor =
        sqrt(2.0f / (pi * z))
        * exp(imag_unit * (z - 0.5f * static_cast<float>(order) * pi - 0.25f * pi));

    complex<float> series(1.0f, 0.0f);
    const complex<float> inv_z = 1.0f / z;
    complex<float> inv_z_power(1.0f, 0.0f);
    complex<float> imag_power(1.0f, 0.0f);
    float coeff = 1.0f;
    for (int k = 1; k < 6; ++k) {
        const float odd = static_cast<float>(2 * k - 1);
        coeff *= (mu - odd * odd) / (static_cast<float>(k) * 8.0f);
        inv_z_power *= inv_z;
        imag_power *= imag_unit;
        series += imag_power * coeff * inv_z_power;
    }
    return prefactor * series;
}

__device__ inline void hankel_orders01_complex(
    const complex<float>& z,
    complex<float>& h0,
    complex<float>& h1)
{
    const float magnitude = complex_abs_f(z);
    if (magnitude < 6.5f) {
        hankel_series_orders01(z, h0, h1);
        return;
    }
    h0 = hankel_asymptotic(z, 0);
    h1 = hankel_asymptotic(z, 1);
}
"""


COMPLEX64_REDUCTION_DEVICE_HELPERS = r"""
__device__ inline complex<float> warp_reduce_complex_sum(complex<float> value) {
    const unsigned int mask = 0xffffffffu;
    for (int offset = warpSize / 2; offset > 0; offset >>= 1) {
        value += complex<float>(
            __shfl_down_sync(mask, value.real(), offset),
            __shfl_down_sync(mask, value.imag(), offset)
        );
    }
    return value;
}

template <int NumWarps>
__device__ inline complex<float> block_reduce_complex_sum(
    complex<float> value,
    complex<float>* shared)
{
    const int lane = threadIdx.x & (warpSize - 1);
    const int warp = threadIdx.x / warpSize;
    value = warp_reduce_complex_sum(value);
    if (lane == 0) {
        shared[warp] = value;
    }
    __syncthreads();
    if (warp == 0) {
        value = lane < NumWarps ? shared[lane] : complex<float>(0.0f, 0.0f);
        value = warp_reduce_complex_sum(value);
    }
    return value;
}
"""


def apply_float_precision_to_cuda_source(source: str) -> str:
    updated = source.replace("complex<double>", "complex<float>")
    updated = re.sub(r"\bdouble\b", "float", updated)
    updated = re.sub(r"\bj0\(", "j0f(", updated)
    updated = re.sub(r"\bj1\(", "j1f(", updated)
    updated = re.sub(r"\by0\(", "y0f(", updated)
    updated = re.sub(r"\by1\(", "y1f(", updated)
    updated = re.sub(r"\bhypot\(", "hypotf(", updated)
    updated = re.sub(r"\bfmax\(", "fmaxf(", updated)
    return updated
