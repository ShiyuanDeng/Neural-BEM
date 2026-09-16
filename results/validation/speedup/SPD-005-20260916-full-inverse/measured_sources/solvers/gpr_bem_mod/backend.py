"""Optional array backends for accelerated operator assembly."""

from __future__ import annotations

from dataclasses import dataclass
import re
import warnings

import numpy as np
from scipy.special import hankel1 as scipy_hankel1

from .precision import resolve_precision_policy


@dataclass(frozen=True)
class AssemblyBackend:
    """Array backend used for local block assembly."""

    name: str
    xp: object
    hankel1: object
    hankel1_real: object | None = None
    hankel1_orders01_real: object | None = None
    scatter_add: object | None = None
    batched_solve: object | None = None
    batched_solve_default_limit: int | None = None
    batched_solve_max_n: int | None = None
    kernel_provider: object | None = None
    is_gpu: bool = False
    complex_dtype: object = np.complex128
    real_dtype: object = np.float64
    complex_precision: str = "complex128"
    precision_policy: str = "stable"
    resolved_complex_kernel_policy: str = "off"
    experimental_fp32_complex_regular_kernel: bool = False
    experimental_fp32_complex_kernel_policy: str = "off"

    def asarray(self, array):
        return self.xp.asarray(array)

    def ascomplex(self, array):
        return self.xp.asarray(array, dtype=self.complex_dtype)

    def asreal(self, array):
        return self.xp.asarray(array, dtype=self.real_dtype)

    def to_host(self, array) -> np.ndarray:
        if self.is_gpu:
            return self.xp.asnumpy(array)
        return np.asarray(array)

    def add_at(self, array, indices, values) -> None:
        if self.scatter_add is not None:
            if self.xp.iscomplexobj(array) or self.xp.iscomplexobj(values):
                self.scatter_add(array.real, indices, self.xp.real(values))
                self.scatter_add(array.imag, indices, self.xp.imag(values))
            else:
                self.scatter_add(array, indices, values)
            return
        np.add.at(array, indices, values)


def _numpy_backend() -> AssemblyBackend:
    def numpy_hankel1_real(order: int, z):
        return scipy_hankel1(order, z)

    def numpy_hankel1_orders01_real(z):
        return scipy_hankel1(0, z), scipy_hankel1(1, z)

    return AssemblyBackend(
        name="numpy",
        xp=np,
        hankel1=scipy_hankel1,
        hankel1_real=numpy_hankel1_real,
        hankel1_orders01_real=numpy_hankel1_orders01_real,
        is_gpu=False,
        complex_dtype=np.complex128,
        real_dtype=np.float64,
        complex_precision="complex128",
        precision_policy="stable",
        resolved_complex_kernel_policy="off",
    )


def _apply_float_precision_to_cuda_source(source: str) -> str:
    updated = source.replace("complex<double>", "complex<float>")
    updated = re.sub(r"\bdouble\b", "float", updated)
    updated = re.sub(r"\bj0\(", "j0f(", updated)
    updated = re.sub(r"\bj1\(", "j1f(", updated)
    updated = re.sub(r"\by0\(", "y0f(", updated)
    updated = re.sub(r"\by1\(", "y1f(", updated)
    updated = re.sub(r"\bhypot\(", "hypotf(", updated)
    updated = re.sub(r"\bfmax\(", "fmaxf(", updated)
    return updated


def get_assembly_backend(
    name: str = "auto",
    complex_precision: str = "complex128",
    precision_policy: str = "stable",
    experimental_fp32_complex_regular_kernel: bool = False,
    experimental_fp32_complex_kernel_policy: str = "off",
) -> AssemblyBackend:
    """Return the requested assembly backend.

    `auto` prefers CuPy when available and otherwise falls back to NumPy.
    """

    normalized = name.strip().lower()
    normalized_precision = complex_precision.strip().lower()
    if normalized_precision not in {"complex128", "complex64"}:
        raise ValueError("complex_precision must be 'complex128' or 'complex64'.")
    normalized_precision_policy, normalized_legacy_policy, resolved_policy_for_cupy = resolve_precision_policy(
        precision_policy,
        complex_precision=normalized_precision,
        backend_name="cupy",
        experimental_fp32_complex_regular_kernel=experimental_fp32_complex_regular_kernel,
        experimental_fp32_complex_kernel_policy=experimental_fp32_complex_kernel_policy,
    )
    _, _, resolved_policy_for_numpy = resolve_precision_policy(
        precision_policy,
        complex_precision=normalized_precision,
        backend_name="numpy",
        experimental_fp32_complex_regular_kernel=experimental_fp32_complex_regular_kernel,
        experimental_fp32_complex_kernel_policy=experimental_fp32_complex_kernel_policy,
    )
    if normalized in {"auto", "cupy"}:
        try:
            import cupy as cp
            import cupy.cublas as cupy_cublas
            from cupyx import scatter_add as cupy_scatter_add
            from cupyx.scipy.special import j0 as cupy_j0
            from cupyx.scipy.special import j1 as cupy_j1
            from cupyx.scipy.special import y0 as cupy_y0
            from cupyx.scipy.special import y1 as cupy_y1

            complex_hankel_module = None
            complex_hankel_kernels: dict[str, object] = {}
            target_complex_dtype = cp.complex64 if normalized_precision == "complex64" else cp.complex128
            target_real_dtype = cp.float32 if normalized_precision == "complex64" else cp.float64

            def get_complex_hankel_kernel(order: int):
                nonlocal complex_hankel_module
                kernel_name = f"hankel{order}_complex_kernel"
                if kernel_name not in complex_hankel_kernels:
                    if complex_hankel_module is None:
                        complex_hankel_module = cp.RawModule(
                            code=r"""
#include <cupy/complex.cuh>

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

extern "C" __global__ void hankel0_complex_kernel(
    const complex<double>* z,
    const long long n,
    complex<double>* out)
{
    const long long idx = static_cast<long long>(blockDim.x) * static_cast<long long>(blockIdx.x)
        + static_cast<long long>(threadIdx.x);
    if (idx >= n) {
        return;
    }
    complex<double> h0, h1;
    hankel_orders01_complex(z[idx], h0, h1);
    out[idx] = h0;
}

extern "C" __global__ void hankel1_complex_kernel(
    const complex<double>* z,
    const long long n,
    complex<double>* out)
{
    const long long idx = static_cast<long long>(blockDim.x) * static_cast<long long>(blockIdx.x)
        + static_cast<long long>(threadIdx.x);
    if (idx >= n) {
        return;
    }
    complex<double> h0, h1;
    hankel_orders01_complex(z[idx], h0, h1);
    out[idx] = h1;
}
""",
                            options=("-std=c++11",),
                            name_expressions=("hankel0_complex_kernel", "hankel1_complex_kernel"),
                        )
                        if normalized_precision == "complex64":
                            complex_hankel_module = cp.RawModule(
                                code=_apply_float_precision_to_cuda_source(
                                    r"""
#include <cupy/complex.cuh>

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

extern "C" __global__ void hankel0_complex_kernel(
    const complex<double>* z,
    const long long n,
    complex<double>* out)
{
    const long long idx = static_cast<long long>(blockDim.x) * static_cast<long long>(blockIdx.x)
        + static_cast<long long>(threadIdx.x);
    if (idx >= n) {
        return;
    }
    complex<double> h0, h1;
    hankel_orders01_complex(z[idx], h0, h1);
    out[idx] = h0;
}

extern "C" __global__ void hankel1_complex_kernel(
    const complex<double>* z,
    const long long n,
    complex<double>* out)
{
    const long long idx = static_cast<long long>(blockDim.x) * static_cast<long long>(blockIdx.x)
        + static_cast<long long>(threadIdx.x);
    if (idx >= n) {
        return;
    }
    complex<double> h0, h1;
    hankel_orders01_complex(z[idx], h0, h1);
    out[idx] = h1;
}
"""
                                ),
                                options=("-std=c++11",),
                                name_expressions=("hankel0_complex_kernel", "hankel1_complex_kernel"),
                            )
                    complex_hankel_kernels[kernel_name] = complex_hankel_module.get_function(kernel_name)
                return complex_hankel_kernels[kernel_name]

            def cupy_hankel1(order: int, z):
                value = z if isinstance(z, cp.ndarray) else cp.asarray(z)
                if cp.iscomplexobj(value):
                    imag_part = cp.imag(value)
                    if bool(cp.any(cp.abs(imag_part) > 1.0e-14).item()):
                        if order in {0, 1}:
                            value_complex = value.astype(target_complex_dtype, copy=False)
                            flat = value_complex.reshape(-1)
                            out = cp.empty_like(flat)
                            threads = 128
                            blocks = (int(flat.size) + threads - 1) // threads
                            get_complex_hankel_kernel(order)(
                                (blocks,),
                                (threads,),
                                (flat, np.int64(flat.size), out),
                            )
                            return out.reshape(value.shape)
                        return cp.asarray(scipy_hankel1(order, cp.asnumpy(value)), dtype=target_complex_dtype)
                    value = cp.real(value)

                if order == 0:
                    return (cupy_j0(value) + 1j * cupy_y0(value)).astype(target_complex_dtype, copy=False)
                if order == 1:
                    return (cupy_j1(value) + 1j * cupy_y1(value)).astype(target_complex_dtype, copy=False)
                return cp.asarray(scipy_hankel1(order, cp.asnumpy(value)), dtype=target_complex_dtype)

            def cupy_hankel1_real(order: int, z):
                value = z if isinstance(z, cp.ndarray) else cp.asarray(z)
                if order == 0:
                    return (cupy_j0(value) + 1j * cupy_y0(value)).astype(target_complex_dtype, copy=False)
                if order == 1:
                    return (cupy_j1(value) + 1j * cupy_y1(value)).astype(target_complex_dtype, copy=False)
                raise ValueError("CuPy Hankel wrapper only supports orders 0 and 1.")

            def cupy_hankel1_orders01_real(z):
                value = z if isinstance(z, cp.ndarray) else cp.asarray(z)
                return (
                    (cupy_j0(value) + 1j * cupy_y0(value)).astype(target_complex_dtype, copy=False),
                    (cupy_j1(value) + 1j * cupy_y1(value)).astype(target_complex_dtype, copy=False),
                )

            def cupy_batched_solve(a, b):
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r"The matrix size \([0-9]+\) exceeds the set limit \([0-9]+\)",
                        category=UserWarning,
                    )
                    return cupy_cublas.batched_gesv(a, b)

            try:
                cp.cuda.runtime.getDeviceCount()
            except Exception as exc:
                if normalized == "cupy":
                    raise RuntimeError("CuPy is installed but no working CUDA device is available.") from exc
            else:
                from .cupy_kernel_provider import CuPyKernelProvider

                return AssemblyBackend(
                    name="cupy",
                    xp=cp,
                    hankel1=cupy_hankel1,
                    hankel1_real=cupy_hankel1_real,
                    hankel1_orders01_real=cupy_hankel1_orders01_real,
                    scatter_add=cupy_scatter_add,
                    batched_solve=cupy_batched_solve,
                    batched_solve_default_limit=int(cupy_cublas.get_batched_gesv_limit()),
                    batched_solve_max_n=512,
                    kernel_provider=CuPyKernelProvider(
                        cp,
                        complex_precision=normalized_precision,
                        precision_policy=normalized_precision_policy,
                        experimental_fp32_complex_regular_kernel=experimental_fp32_complex_regular_kernel,
                        experimental_fp32_complex_kernel_policy=normalized_legacy_policy,
                    ),
                    is_gpu=True,
                    complex_dtype=target_complex_dtype,
                    real_dtype=target_real_dtype,
                    complex_precision=normalized_precision,
                    precision_policy=normalized_precision_policy,
                    resolved_complex_kernel_policy=resolved_policy_for_cupy,
                    experimental_fp32_complex_regular_kernel=experimental_fp32_complex_regular_kernel,
                    experimental_fp32_complex_kernel_policy=normalized_legacy_policy,
                )
        except Exception as exc:
            if normalized == "cupy":
                raise RuntimeError("CuPy assembly backend requested but unavailable.") from exc

    if normalized not in {"auto", "numpy"}:
        raise ValueError(f"Unsupported assembly backend: {name}")
    if normalized_precision == "complex64":
        backend = _numpy_backend()
        return AssemblyBackend(
            name=backend.name,
            xp=backend.xp,
            hankel1=backend.hankel1,
            hankel1_real=backend.hankel1_real,
            hankel1_orders01_real=backend.hankel1_orders01_real,
            scatter_add=backend.scatter_add,
            batched_solve=backend.batched_solve,
            batched_solve_default_limit=backend.batched_solve_default_limit,
            batched_solve_max_n=backend.batched_solve_max_n,
            kernel_provider=backend.kernel_provider,
            is_gpu=backend.is_gpu,
            complex_dtype=np.complex64,
            real_dtype=np.float32,
            complex_precision=normalized_precision,
            precision_policy=normalized_precision_policy,
            resolved_complex_kernel_policy=resolved_policy_for_numpy,
            experimental_fp32_complex_regular_kernel=experimental_fp32_complex_regular_kernel,
            experimental_fp32_complex_kernel_policy=normalized_legacy_policy,
        )
    backend = _numpy_backend()
    return AssemblyBackend(
        name=backend.name,
        xp=backend.xp,
        hankel1=backend.hankel1,
        hankel1_real=backend.hankel1_real,
        hankel1_orders01_real=backend.hankel1_orders01_real,
        scatter_add=backend.scatter_add,
        batched_solve=backend.batched_solve,
        batched_solve_default_limit=backend.batched_solve_default_limit,
        batched_solve_max_n=backend.batched_solve_max_n,
        kernel_provider=backend.kernel_provider,
        is_gpu=backend.is_gpu,
        complex_dtype=backend.complex_dtype,
        real_dtype=backend.real_dtype,
        complex_precision=backend.complex_precision,
        precision_policy=normalized_precision_policy,
        resolved_complex_kernel_policy=resolved_policy_for_numpy,
        experimental_fp32_complex_regular_kernel=experimental_fp32_complex_regular_kernel,
        experimental_fp32_complex_kernel_policy=normalized_legacy_policy,
    )
