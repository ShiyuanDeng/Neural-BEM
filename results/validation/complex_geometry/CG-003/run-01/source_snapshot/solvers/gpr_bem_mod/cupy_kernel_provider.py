"""CuPy RawKernel registry for TMz BEM GPU kernels."""

from __future__ import annotations

from .cupy_kernel_sources import (
    COMPLEX64_REDUCTION_DEVICE_HELPERS,
    COMPLEX64_REGULAR_HANKEL_ORDERS01_DEVICE_HELPERS,
    COMPLEX_HANKEL_ORDERS01_DEVICE_HELPERS,
    COMPLEX_REDUCTION_DEVICE_HELPERS,
    apply_float_precision_to_cuda_source,
    complex_hankel_device_helpers_with_params,
    complex_pair_threads,
    sanitize_identifier,
)
from .precision import resolve_precision_policy


class CuPyKernelProvider:
    """Build and cache CuPy kernels independently from solver code."""

    def __init__(
        self,
        cp_module,
        complex_precision: str = "complex128",
        precision_policy: str = "stable",
        experimental_fp32_complex_regular_kernel: bool = False,
        experimental_fp32_complex_kernel_policy: str = "off",
    ) -> None:
        self._cp = cp_module
        self._complex_precision = complex_precision.strip().lower()
        if self._complex_precision not in {"complex128", "complex64"}:
            raise ValueError("complex_precision must be 'complex128' or 'complex64'.")
        normalized_precision_policy, normalized_policy, resolved_policy = resolve_precision_policy(
            precision_policy,
            complex_precision=self._complex_precision,
            backend_name="cupy",
            experimental_fp32_complex_regular_kernel=experimental_fp32_complex_regular_kernel,
            experimental_fp32_complex_kernel_policy=experimental_fp32_complex_kernel_policy,
        )
        self._precision_policy = normalized_precision_policy
        self._experimental_fp32_complex_regular_kernel = bool(experimental_fp32_complex_regular_kernel)
        self._experimental_fp32_complex_kernel_policy = normalized_policy
        self._resolved_complex_kernel_policy = resolved_policy
        self._pair_kernels: dict[tuple[str, int], tuple[object, int]] = {}
        self._pair_complex_kernels: dict[tuple[str, int], tuple[object, int]] = {}
        self._singular_remainder_kernels: dict[tuple[str, int], tuple[object, int]] = {}
        self._singular_remainder_complex_kernels: dict[tuple[str, int], tuple[object, int]] = {}
        self._projection_pair_kernels: dict[tuple[str, int], tuple[object, int]] = {}
        self._projection_pair_dual_kernels: dict[int, tuple[object, int]] = {}
        self._projection_pair_complex_dual_kernels: dict[int, tuple[object, int]] = {}
        self._potential_pair_kernels: dict[tuple[str, int], tuple[object, int]] = {}
        self._potential_pair_dual_kernels: dict[int, tuple[object, int]] = {}
        self._potential_pair_complex_dual_kernels: dict[int, tuple[object, int]] = {}
        self._incident_receiver_complex_kernels: dict[str, tuple[object, int]] = {}

    def use_fp32_complex_pair_kernel(self, relation: str) -> bool:
        if self._complex_precision == "complex64":
            return True
        if self._resolved_complex_kernel_policy == "regular":
            return relation == "regular"
        if self._resolved_complex_kernel_policy == "regular_near":
            return relation in {"regular", "near"}
        if self._resolved_complex_kernel_policy == "regular_near_adjacent":
            return relation in {"regular", "near", "adjacent"}
        return False

    def use_fp32_complex_singular_kernel(self, kernel_group: str) -> bool:
        if self._complex_precision == "complex64":
            return True
        return self._resolved_complex_kernel_policy == "regular_near_adjacent" and kernel_group.startswith("adjacent_")

    def use_fp32_complex_rhs_kernels(self) -> bool:
        return self._complex_precision == "complex64" or self._resolved_complex_kernel_policy in {"regular_near", "regular_near_adjacent"}

    def _build_module(self, code: str, name_expressions: tuple[str, ...], force_float_precision: bool = False):
        source = code
        if self._complex_precision == "complex64" or force_float_precision:
            source = apply_float_precision_to_cuda_source(source)
        return self._cp.RawModule(
            code=source,
            options=("-std=c++11",),
            name_expressions=name_expressions,
        )

    def get_pair_kernel(self, relation: str, num_quadrature: int) -> tuple[object, int]:
        cache_key = (relation, int(num_quadrature))
        if cache_key not in self._pair_kernels:
            threads = 128
            relation_id = sanitize_identifier(relation)
            kernel_name = f"assemble_pair_batch_{relation_id}_{num_quadrature}"
            source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const double* weights,
    const double* source_factors,
    const double* phi_products,
    const double* derivative_outer,
    const double* n_dot_n,
    const complex<double>* wavenumbers,
    const int num_pairs,
    complex<double>* v_out,
    complex<double>* k_out,
    complex<double>* w_out)
{{
    const int pair = blockIdx.x;
    const int widx = blockIdx.y;
    const int tid = threadIdx.x;
    if (pair >= num_pairs) {{
        return;
    }}

    complex<double> v00(0.0, 0.0), v01(0.0, 0.0), v10(0.0, 0.0), v11(0.0, 0.0);
    complex<double> k00(0.0, 0.0), k01(0.0, 0.0), k10(0.0, 0.0), k11(0.0, 0.0);
    complex<double> sum_green(0.0, 0.0);

    const int pair_offset = pair * NUM_Q;
    const complex<double> green_scale(0.0, 0.25);
    const complex<double> normal_scale = green_scale * wavenumbers[widx];
    const double real_wavenumber = wavenumbers[widx].real();

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const double argument = real_wavenumber * distances[pair_offset + q];
        const complex<double> h0(j0(argument), y0(argument));
        const complex<double> h1(j1(argument), y1(argument));
        const complex<double> green = green_scale * h0 * weights[pair_offset + q];
        const complex<double> normal =
            normal_scale * h1 * (weights[pair_offset + q] * source_factors[pair_offset + q]);

        const double phi00 = phi_products[q];
        const double phi01 = phi_products[NUM_Q + q];
        const double phi10 = phi_products[2 * NUM_Q + q];
        const double phi11 = phi_products[3 * NUM_Q + q];

        v00 += green * phi00;
        v01 += green * phi01;
        v10 += green * phi10;
        v11 += green * phi11;

        k00 += normal * phi00;
        k01 += normal * phi01;
        k10 += normal * phi10;
        k11 += normal * phi11;

        sum_green += green;
    }}

    __shared__ complex<double> shared_v00[THREADS];
    __shared__ complex<double> shared_v01[THREADS];
    __shared__ complex<double> shared_v10[THREADS];
    __shared__ complex<double> shared_v11[THREADS];
    __shared__ complex<double> shared_k00[THREADS];
    __shared__ complex<double> shared_k01[THREADS];
    __shared__ complex<double> shared_k10[THREADS];
    __shared__ complex<double> shared_k11[THREADS];
    __shared__ complex<double> shared_sum_green[THREADS];

    shared_v00[tid] = v00;
    shared_v01[tid] = v01;
    shared_v10[tid] = v10;
    shared_v11[tid] = v11;
    shared_k00[tid] = k00;
    shared_k01[tid] = k01;
    shared_k10[tid] = k10;
    shared_k11[tid] = k11;
    shared_sum_green[tid] = sum_green;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_v00[tid] += shared_v00[tid + stride];
            shared_v01[tid] += shared_v01[tid + stride];
            shared_v10[tid] += shared_v10[tid + stride];
            shared_v11[tid] += shared_v11[tid + stride];
            shared_k00[tid] += shared_k00[tid + stride];
            shared_k01[tid] += shared_k01[tid + stride];
            shared_k10[tid] += shared_k10[tid + stride];
            shared_k11[tid] += shared_k11[tid + stride];
            shared_sum_green[tid] += shared_sum_green[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        const int out_offset = ((widx * num_pairs) + pair) * 4;
        v_out[out_offset + 0] = shared_v00[0];
        v_out[out_offset + 1] = shared_v01[0];
        v_out[out_offset + 2] = shared_v10[0];
        v_out[out_offset + 3] = shared_v11[0];

        k_out[out_offset + 0] = shared_k00[0];
        k_out[out_offset + 1] = shared_k01[0];
        k_out[out_offset + 2] = shared_k10[0];
        k_out[out_offset + 3] = shared_k11[0];

        const complex<double> k_squared = wavenumbers[widx] * wavenumbers[widx];
        const double ndn = n_dot_n[pair];
        const int deriv_offset = pair * 4;

        w_out[out_offset + 0] = derivative_outer[deriv_offset + 0] * shared_sum_green[0] - k_squared * ndn * shared_v00[0];
        w_out[out_offset + 1] = derivative_outer[deriv_offset + 1] * shared_sum_green[0] - k_squared * ndn * shared_v01[0];
        w_out[out_offset + 2] = derivative_outer[deriv_offset + 2] * shared_sum_green[0] - k_squared * ndn * shared_v10[0];
        w_out[out_offset + 3] = derivative_outer[deriv_offset + 3] * shared_sum_green[0] - k_squared * ndn * shared_v11[0];
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._pair_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._pair_kernels[cache_key]

    def get_pair_complex_kernel(self, relation: str, num_quadrature: int) -> tuple[object, int]:
        variant = "fp32" if self.use_fp32_complex_pair_kernel(relation) else self._complex_precision
        cache_key = (relation, int(num_quadrature), variant)
        if cache_key not in self._pair_complex_kernels:
            relation_id = sanitize_identifier(relation)
            kernel_name = f"assemble_pair_batch_complex_{relation_id}_{num_quadrature}"
            if variant == "fp32":
                threads = 128
                source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}
#define NUM_WARPS ((THREADS + 31) / 32)

{COMPLEX64_REGULAR_HANKEL_ORDERS01_DEVICE_HELPERS}
{COMPLEX64_REDUCTION_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const float* distances,
    const float* weights,
    const float* source_factors,
    const float* phi_products,
    const float* derivative_outer,
    const float* n_dot_n,
    const complex<float>* wavenumbers,
    const int num_pairs,
    complex<float>* v_out,
    complex<float>* k_out,
    complex<float>* w_out)
{{
    const int pair = blockIdx.x;
    const int widx = blockIdx.y;
    const int tid = threadIdx.x;
    if (pair >= num_pairs) {{
        return;
    }}

    complex<float> v00(0.0f, 0.0f), v01(0.0f, 0.0f), v10(0.0f, 0.0f), v11(0.0f, 0.0f);
    complex<float> k00(0.0f, 0.0f), k01(0.0f, 0.0f), k10(0.0f, 0.0f), k11(0.0f, 0.0f);
    complex<float> sum_green(0.0f, 0.0f);

    const int pair_offset = pair * NUM_Q;
    const complex<float> green_scale(0.0f, 0.25f);
    const complex<float> wavenumber = wavenumbers[widx];
    const complex<float> normal_scale = green_scale * wavenumber;

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<float> argument = wavenumber * distances[pair_offset + q];
        complex<float> h0, h1;
        hankel_orders01_complex(argument, h0, h1);
        const complex<float> green = green_scale * h0 * weights[pair_offset + q];
        const complex<float> normal =
            normal_scale * h1 * (weights[pair_offset + q] * source_factors[pair_offset + q]);

        const float phi00 = phi_products[q];
        const float phi01 = phi_products[NUM_Q + q];
        const float phi10 = phi_products[2 * NUM_Q + q];
        const float phi11 = phi_products[3 * NUM_Q + q];

        v00 += green * phi00;
        v01 += green * phi01;
        v10 += green * phi10;
        v11 += green * phi11;

        k00 += normal * phi00;
        k01 += normal * phi01;
        k10 += normal * phi10;
        k11 += normal * phi11;

        sum_green += green;
    }}

    __shared__ complex<float> shared_v00[NUM_WARPS];
    __shared__ complex<float> shared_v01[NUM_WARPS];
    __shared__ complex<float> shared_v10[NUM_WARPS];
    __shared__ complex<float> shared_v11[NUM_WARPS];
    __shared__ complex<float> shared_k00[NUM_WARPS];
    __shared__ complex<float> shared_k01[NUM_WARPS];
    __shared__ complex<float> shared_k10[NUM_WARPS];
    __shared__ complex<float> shared_k11[NUM_WARPS];
    __shared__ complex<float> shared_sum_green[NUM_WARPS];

    v00 = block_reduce_complex_sum<NUM_WARPS>(v00, shared_v00);
    v01 = block_reduce_complex_sum<NUM_WARPS>(v01, shared_v01);
    v10 = block_reduce_complex_sum<NUM_WARPS>(v10, shared_v10);
    v11 = block_reduce_complex_sum<NUM_WARPS>(v11, shared_v11);
    k00 = block_reduce_complex_sum<NUM_WARPS>(k00, shared_k00);
    k01 = block_reduce_complex_sum<NUM_WARPS>(k01, shared_k01);
    k10 = block_reduce_complex_sum<NUM_WARPS>(k10, shared_k10);
    k11 = block_reduce_complex_sum<NUM_WARPS>(k11, shared_k11);
    sum_green = block_reduce_complex_sum<NUM_WARPS>(sum_green, shared_sum_green);

    if (tid == 0) {{
        const int out_offset = ((widx * num_pairs) + pair) * 4;
        v_out[out_offset + 0] = v00;
        v_out[out_offset + 1] = v01;
        v_out[out_offset + 2] = v10;
        v_out[out_offset + 3] = v11;

        k_out[out_offset + 0] = k00;
        k_out[out_offset + 1] = k01;
        k_out[out_offset + 2] = k10;
        k_out[out_offset + 3] = k11;

        const complex<float> k_squared = wavenumber * wavenumber;
        const float ndn = n_dot_n[pair];
        const int deriv_offset = pair * 4;

        w_out[out_offset + 0] = derivative_outer[deriv_offset + 0] * sum_green - k_squared * ndn * v00;
        w_out[out_offset + 1] = derivative_outer[deriv_offset + 1] * sum_green - k_squared * ndn * v01;
        w_out[out_offset + 2] = derivative_outer[deriv_offset + 2] * sum_green - k_squared * ndn * v10;
        w_out[out_offset + 3] = derivative_outer[deriv_offset + 3] * sum_green - k_squared * ndn * v11;
    }}
}}
"""
            else:
                threads = complex_pair_threads(relation, num_quadrature)
                hankel_helpers = (
                    complex_hankel_device_helpers_with_params(8.5, 8)
                    if relation == "regular"
                    else COMPLEX_HANKEL_ORDERS01_DEVICE_HELPERS
                )
                source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}
#define NUM_WARPS ((THREADS + 31) / 32)

{hankel_helpers}
{COMPLEX_REDUCTION_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const double* weights,
    const double* source_factors,
    const double* phi_products,
    const double* derivative_outer,
    const double* n_dot_n,
    const complex<double>* wavenumbers,
    const int num_pairs,
    complex<double>* v_out,
    complex<double>* k_out,
    complex<double>* w_out)
{{
    const int pair = blockIdx.x;
    const int widx = blockIdx.y;
    const int tid = threadIdx.x;
    if (pair >= num_pairs) {{
        return;
    }}

    complex<double> v00(0.0, 0.0), v01(0.0, 0.0), v10(0.0, 0.0), v11(0.0, 0.0);
    complex<double> k00(0.0, 0.0), k01(0.0, 0.0), k10(0.0, 0.0), k11(0.0, 0.0);
    complex<double> sum_green(0.0, 0.0);

    const int pair_offset = pair * NUM_Q;
    const complex<double> green_scale(0.0, 0.25);
    const complex<double> wavenumber = wavenumbers[widx];
    const complex<double> normal_scale = green_scale * wavenumber;

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<double> argument = wavenumber * distances[pair_offset + q];
        complex<double> h0, h1;
        hankel_orders01_complex(argument, h0, h1);
        const complex<double> green = green_scale * h0 * weights[pair_offset + q];
        const complex<double> normal =
            normal_scale * h1 * (weights[pair_offset + q] * source_factors[pair_offset + q]);

        const double phi00 = phi_products[q];
        const double phi01 = phi_products[NUM_Q + q];
        const double phi10 = phi_products[2 * NUM_Q + q];
        const double phi11 = phi_products[3 * NUM_Q + q];

        v00 += green * phi00;
        v01 += green * phi01;
        v10 += green * phi10;
        v11 += green * phi11;

        k00 += normal * phi00;
        k01 += normal * phi01;
        k10 += normal * phi10;
        k11 += normal * phi11;

        sum_green += green;
    }}

    __shared__ complex<double> shared_v00[NUM_WARPS];
    __shared__ complex<double> shared_v01[NUM_WARPS];
    __shared__ complex<double> shared_v10[NUM_WARPS];
    __shared__ complex<double> shared_v11[NUM_WARPS];
    __shared__ complex<double> shared_k00[NUM_WARPS];
    __shared__ complex<double> shared_k01[NUM_WARPS];
    __shared__ complex<double> shared_k10[NUM_WARPS];
    __shared__ complex<double> shared_k11[NUM_WARPS];
    __shared__ complex<double> shared_sum_green[NUM_WARPS];

    v00 = block_reduce_complex_sum<NUM_WARPS>(v00, shared_v00);
    v01 = block_reduce_complex_sum<NUM_WARPS>(v01, shared_v01);
    v10 = block_reduce_complex_sum<NUM_WARPS>(v10, shared_v10);
    v11 = block_reduce_complex_sum<NUM_WARPS>(v11, shared_v11);
    k00 = block_reduce_complex_sum<NUM_WARPS>(k00, shared_k00);
    k01 = block_reduce_complex_sum<NUM_WARPS>(k01, shared_k01);
    k10 = block_reduce_complex_sum<NUM_WARPS>(k10, shared_k10);
    k11 = block_reduce_complex_sum<NUM_WARPS>(k11, shared_k11);
    sum_green = block_reduce_complex_sum<NUM_WARPS>(sum_green, shared_sum_green);

    if (tid == 0) {{
        const int out_offset = ((widx * num_pairs) + pair) * 4;
        v_out[out_offset + 0] = v00;
        v_out[out_offset + 1] = v01;
        v_out[out_offset + 2] = v10;
        v_out[out_offset + 3] = v11;

        k_out[out_offset + 0] = k00;
        k_out[out_offset + 1] = k01;
        k_out[out_offset + 2] = k10;
        k_out[out_offset + 3] = k11;

        const complex<double> k_squared = wavenumber * wavenumber;
        const double ndn = n_dot_n[pair];
        const int deriv_offset = pair * 4;

        w_out[out_offset + 0] = derivative_outer[deriv_offset + 0] * sum_green - k_squared * ndn * v00;
        w_out[out_offset + 1] = derivative_outer[deriv_offset + 1] * sum_green - k_squared * ndn * v01;
        w_out[out_offset + 2] = derivative_outer[deriv_offset + 2] * sum_green - k_squared * ndn * v10;
        w_out[out_offset + 3] = derivative_outer[deriv_offset + 3] * sum_green - k_squared * ndn * v11;
    }}
}}
"""
            module = self._build_module(source, (kernel_name,), force_float_precision=False)
            self._pair_complex_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._pair_complex_kernels[cache_key]

    def get_singular_remainder_kernel(self, kernel_group: str, num_quadrature: int) -> tuple[object, int]:
        cache_key = (kernel_group, int(num_quadrature))
        if cache_key not in self._singular_remainder_kernels:
            threads = 128
            group_id = sanitize_identifier(kernel_group)
            kernel_name = f"assemble_singular_remainder_{group_id}_{num_quadrature}"
            source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const double* weights,
    const double* source_factors,
    const complex<double>* green_log_weighted,
    const complex<double>* normal_singular_weighted,
    const double* phi_products,
    const complex<double>* green_constants,
    const complex<double>* wavenumbers,
    const int num_pairs,
    complex<double>* v_out,
    complex<double>* k_out,
    complex<double>* green_sum_out)
{{
    const int pair = blockIdx.x;
    const int widx = blockIdx.y;
    const int tid = threadIdx.x;
    if (pair >= num_pairs) {{
        return;
    }}

    complex<double> v00(0.0, 0.0), v01(0.0, 0.0), v10(0.0, 0.0), v11(0.0, 0.0);
    complex<double> k00(0.0, 0.0), k01(0.0, 0.0), k10(0.0, 0.0), k11(0.0, 0.0);
    complex<double> sum_green(0.0, 0.0);

    const int pair_offset = pair * NUM_Q;
    const complex<double> green_scale(0.0, 0.25);
    const complex<double> normal_scale = green_scale * wavenumbers[widx];
    const complex<double> green_constant = green_constants[widx];
    const double real_wavenumber = wavenumbers[widx].real();

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const double argument = real_wavenumber * distances[pair_offset + q];
        const complex<double> h0(j0(argument), y0(argument));
        const complex<double> h1(j1(argument), y1(argument));
        const complex<double> weighted_green =
            green_scale * h0 * weights[pair_offset + q];
        const complex<double> green =
            weighted_green
            - green_log_weighted[pair_offset + q]
            - green_constant * weights[pair_offset + q];

        const complex<double> weighted_normal =
            normal_scale * h1 * (weights[pair_offset + q] * source_factors[pair_offset + q]);
        const complex<double> normal =
            weighted_normal - normal_singular_weighted[pair_offset + q];

        const double phi00 = phi_products[q];
        const double phi01 = phi_products[NUM_Q + q];
        const double phi10 = phi_products[2 * NUM_Q + q];
        const double phi11 = phi_products[3 * NUM_Q + q];

        v00 += green * phi00;
        v01 += green * phi01;
        v10 += green * phi10;
        v11 += green * phi11;

        k00 += normal * phi00;
        k01 += normal * phi01;
        k10 += normal * phi10;
        k11 += normal * phi11;

        sum_green += green;
    }}

    __shared__ complex<double> shared_v00[THREADS];
    __shared__ complex<double> shared_v01[THREADS];
    __shared__ complex<double> shared_v10[THREADS];
    __shared__ complex<double> shared_v11[THREADS];
    __shared__ complex<double> shared_k00[THREADS];
    __shared__ complex<double> shared_k01[THREADS];
    __shared__ complex<double> shared_k10[THREADS];
    __shared__ complex<double> shared_k11[THREADS];
    __shared__ complex<double> shared_sum_green[THREADS];

    shared_v00[tid] = v00;
    shared_v01[tid] = v01;
    shared_v10[tid] = v10;
    shared_v11[tid] = v11;
    shared_k00[tid] = k00;
    shared_k01[tid] = k01;
    shared_k10[tid] = k10;
    shared_k11[tid] = k11;
    shared_sum_green[tid] = sum_green;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_v00[tid] += shared_v00[tid + stride];
            shared_v01[tid] += shared_v01[tid + stride];
            shared_v10[tid] += shared_v10[tid + stride];
            shared_v11[tid] += shared_v11[tid + stride];
            shared_k00[tid] += shared_k00[tid + stride];
            shared_k01[tid] += shared_k01[tid + stride];
            shared_k10[tid] += shared_k10[tid + stride];
            shared_k11[tid] += shared_k11[tid + stride];
            shared_sum_green[tid] += shared_sum_green[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        const int out_offset = ((widx * num_pairs) + pair) * 4;
        v_out[out_offset + 0] = shared_v00[0];
        v_out[out_offset + 1] = shared_v01[0];
        v_out[out_offset + 2] = shared_v10[0];
        v_out[out_offset + 3] = shared_v11[0];

        k_out[out_offset + 0] = shared_k00[0];
        k_out[out_offset + 1] = shared_k01[0];
        k_out[out_offset + 2] = shared_k10[0];
        k_out[out_offset + 3] = shared_k11[0];

        green_sum_out[widx * num_pairs + pair] = shared_sum_green[0];
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._singular_remainder_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._singular_remainder_kernels[cache_key]

    def get_singular_remainder_complex_kernel(self, kernel_group: str, num_quadrature: int) -> tuple[object, int]:
        variant = "fp32" if self.use_fp32_complex_singular_kernel(kernel_group) else self._complex_precision
        cache_key = (kernel_group, int(num_quadrature), variant)
        if cache_key not in self._singular_remainder_complex_kernels:
            threads = 128
            group_id = sanitize_identifier(kernel_group)
            kernel_name = f"assemble_singular_remainder_complex_{group_id}_{num_quadrature}"
            if variant == "fp32":
                source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}
#define NUM_WARPS ((THREADS + 31) / 32)

{COMPLEX64_REGULAR_HANKEL_ORDERS01_DEVICE_HELPERS}
{COMPLEX64_REDUCTION_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const float* distances,
    const float* weights,
    const float* source_factors,
    const complex<float>* green_log_weighted,
    const complex<float>* normal_singular_weighted,
    const float* phi_products,
    const complex<float>* green_constants,
    const complex<float>* wavenumbers,
    const int num_pairs,
    complex<float>* v_out,
    complex<float>* k_out,
    complex<float>* green_sum_out)
{{
    const int pair = blockIdx.x;
    const int widx = blockIdx.y;
    const int tid = threadIdx.x;
    if (pair >= num_pairs) {{
        return;
    }}

    complex<float> v00(0.0f, 0.0f), v01(0.0f, 0.0f), v10(0.0f, 0.0f), v11(0.0f, 0.0f);
    complex<float> k00(0.0f, 0.0f), k01(0.0f, 0.0f), k10(0.0f, 0.0f), k11(0.0f, 0.0f);
    complex<float> sum_green(0.0f, 0.0f);

    const int pair_offset = pair * NUM_Q;
    const complex<float> green_scale(0.0f, 0.25f);
    const complex<float> wavenumber = wavenumbers[widx];
    const complex<float> normal_scale = green_scale * wavenumber;
    const complex<float> green_constant = green_constants[widx];

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<float> argument = wavenumber * distances[pair_offset + q];
        complex<float> h0, h1;
        hankel_orders01_complex(argument, h0, h1);
        const complex<float> weighted_green =
            green_scale * h0 * weights[pair_offset + q];
        const complex<float> green =
            weighted_green
            - green_log_weighted[pair_offset + q]
            - green_constant * weights[pair_offset + q];

        const complex<float> weighted_normal =
            normal_scale * h1 * (weights[pair_offset + q] * source_factors[pair_offset + q]);
        const complex<float> normal =
            weighted_normal - normal_singular_weighted[pair_offset + q];

        const float phi00 = phi_products[q];
        const float phi01 = phi_products[NUM_Q + q];
        const float phi10 = phi_products[2 * NUM_Q + q];
        const float phi11 = phi_products[3 * NUM_Q + q];

        v00 += green * phi00;
        v01 += green * phi01;
        v10 += green * phi10;
        v11 += green * phi11;

        k00 += normal * phi00;
        k01 += normal * phi01;
        k10 += normal * phi10;
        k11 += normal * phi11;

        sum_green += green;
    }}

    __shared__ complex<float> shared_v00[NUM_WARPS];
    __shared__ complex<float> shared_v01[NUM_WARPS];
    __shared__ complex<float> shared_v10[NUM_WARPS];
    __shared__ complex<float> shared_v11[NUM_WARPS];
    __shared__ complex<float> shared_k00[NUM_WARPS];
    __shared__ complex<float> shared_k01[NUM_WARPS];
    __shared__ complex<float> shared_k10[NUM_WARPS];
    __shared__ complex<float> shared_k11[NUM_WARPS];
    __shared__ complex<float> shared_sum_green[NUM_WARPS];

    v00 = block_reduce_complex_sum<NUM_WARPS>(v00, shared_v00);
    v01 = block_reduce_complex_sum<NUM_WARPS>(v01, shared_v01);
    v10 = block_reduce_complex_sum<NUM_WARPS>(v10, shared_v10);
    v11 = block_reduce_complex_sum<NUM_WARPS>(v11, shared_v11);
    k00 = block_reduce_complex_sum<NUM_WARPS>(k00, shared_k00);
    k01 = block_reduce_complex_sum<NUM_WARPS>(k01, shared_k01);
    k10 = block_reduce_complex_sum<NUM_WARPS>(k10, shared_k10);
    k11 = block_reduce_complex_sum<NUM_WARPS>(k11, shared_k11);
    sum_green = block_reduce_complex_sum<NUM_WARPS>(sum_green, shared_sum_green);

    if (tid == 0) {{
        const int out_offset = ((widx * num_pairs) + pair) * 4;
        v_out[out_offset + 0] = v00;
        v_out[out_offset + 1] = v01;
        v_out[out_offset + 2] = v10;
        v_out[out_offset + 3] = v11;

        k_out[out_offset + 0] = k00;
        k_out[out_offset + 1] = k01;
        k_out[out_offset + 2] = k10;
        k_out[out_offset + 3] = k11;

        green_sum_out[widx * num_pairs + pair] = sum_green;
    }}
}}
"""
            else:
                source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}
#define NUM_WARPS ((THREADS + 31) / 32)

{COMPLEX_HANKEL_ORDERS01_DEVICE_HELPERS}
{COMPLEX_REDUCTION_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const double* weights,
    const double* source_factors,
    const complex<double>* green_log_weighted,
    const complex<double>* normal_singular_weighted,
    const double* phi_products,
    const complex<double>* green_constants,
    const complex<double>* wavenumbers,
    const int num_pairs,
    complex<double>* v_out,
    complex<double>* k_out,
    complex<double>* green_sum_out)
{{
    const int pair = blockIdx.x;
    const int widx = blockIdx.y;
    const int tid = threadIdx.x;
    if (pair >= num_pairs) {{
        return;
    }}

    complex<double> v00(0.0, 0.0), v01(0.0, 0.0), v10(0.0, 0.0), v11(0.0, 0.0);
    complex<double> k00(0.0, 0.0), k01(0.0, 0.0), k10(0.0, 0.0), k11(0.0, 0.0);
    complex<double> sum_green(0.0, 0.0);

    const int pair_offset = pair * NUM_Q;
    const complex<double> green_scale(0.0, 0.25);
    const complex<double> wavenumber = wavenumbers[widx];
    const complex<double> normal_scale = green_scale * wavenumber;
    const complex<double> green_constant = green_constants[widx];

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<double> argument = wavenumber * distances[pair_offset + q];
        complex<double> h0, h1;
        hankel_orders01_complex(argument, h0, h1);
        const complex<double> weighted_green =
            green_scale * h0 * weights[pair_offset + q];
        const complex<double> green =
            weighted_green
            - green_log_weighted[pair_offset + q]
            - green_constant * weights[pair_offset + q];

        const complex<double> weighted_normal =
            normal_scale * h1 * (weights[pair_offset + q] * source_factors[pair_offset + q]);
        const complex<double> normal =
            weighted_normal - normal_singular_weighted[pair_offset + q];

        const double phi00 = phi_products[q];
        const double phi01 = phi_products[NUM_Q + q];
        const double phi10 = phi_products[2 * NUM_Q + q];
        const double phi11 = phi_products[3 * NUM_Q + q];

        v00 += green * phi00;
        v01 += green * phi01;
        v10 += green * phi10;
        v11 += green * phi11;

        k00 += normal * phi00;
        k01 += normal * phi01;
        k10 += normal * phi10;
        k11 += normal * phi11;

        sum_green += green;
    }}

    __shared__ complex<double> shared_v00[NUM_WARPS];
    __shared__ complex<double> shared_v01[NUM_WARPS];
    __shared__ complex<double> shared_v10[NUM_WARPS];
    __shared__ complex<double> shared_v11[NUM_WARPS];
    __shared__ complex<double> shared_k00[NUM_WARPS];
    __shared__ complex<double> shared_k01[NUM_WARPS];
    __shared__ complex<double> shared_k10[NUM_WARPS];
    __shared__ complex<double> shared_k11[NUM_WARPS];
    __shared__ complex<double> shared_sum_green[NUM_WARPS];

    v00 = block_reduce_complex_sum<NUM_WARPS>(v00, shared_v00);
    v01 = block_reduce_complex_sum<NUM_WARPS>(v01, shared_v01);
    v10 = block_reduce_complex_sum<NUM_WARPS>(v10, shared_v10);
    v11 = block_reduce_complex_sum<NUM_WARPS>(v11, shared_v11);
    k00 = block_reduce_complex_sum<NUM_WARPS>(k00, shared_k00);
    k01 = block_reduce_complex_sum<NUM_WARPS>(k01, shared_k01);
    k10 = block_reduce_complex_sum<NUM_WARPS>(k10, shared_k10);
    k11 = block_reduce_complex_sum<NUM_WARPS>(k11, shared_k11);
    sum_green = block_reduce_complex_sum<NUM_WARPS>(sum_green, shared_sum_green);

    if (tid == 0) {{
        const int out_offset = ((widx * num_pairs) + pair) * 4;
        v_out[out_offset + 0] = v00;
        v_out[out_offset + 1] = v01;
        v_out[out_offset + 2] = v10;
        v_out[out_offset + 3] = v11;

        k_out[out_offset + 0] = k00;
        k_out[out_offset + 1] = k01;
        k_out[out_offset + 2] = k10;
        k_out[out_offset + 3] = k11;

        green_sum_out[widx * num_pairs + pair] = sum_green;
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._singular_remainder_complex_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._singular_remainder_complex_kernels[cache_key]

    def get_projection_pair_kernel(self, kind: str, num_quadrature: int) -> tuple[object, int]:
        cache_key = (kind, int(num_quadrature))
        if cache_key not in self._projection_pair_kernels:
            threads = 128
            kernel_name = f"project_boundary_{sanitize_identifier(kind)}_{num_quadrature}"
            if kind == "dirichlet":
                value_expression = "source_strengths[bidx] * complex<double>(0.0, 0.25) * h_values[h_offset + q]"
            elif kind == "neumann":
                value_expression = (
                    "source_strengths[bidx] * (-complex<double>(0.0, 0.25) * wavenumber) "
                    "* h_values[h_offset + q] * factors[geom_offset + q]"
                )
            else:
                raise ValueError(f"Unsupported projection kernel kind: {kind}")

            source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

extern "C" __global__ void {kernel_name}(
    const complex<double>* h_values,
    const double* weights,
    const double* phi,
    const double* factors,
    const complex<double>* source_strengths,
    const int* panel_nodes,
    const complex<double> wavenumber,
    const int num_panels,
    const int num_point_batches,
    const int num_dofs,
    double* rhs_real,
    double* rhs_imag)
{{
    const int panel = blockIdx.x;
    const int bidx = blockIdx.y;
    const int tid = threadIdx.x;
    if (panel >= num_panels) {{
        return;
    }}

    complex<double> local0(0.0, 0.0), local1(0.0, 0.0);
    const int panel_offset = panel * NUM_Q;
    const int geom_batch = bidx % num_point_batches;
    const int geom_offset = (geom_batch * num_panels + panel) * NUM_Q;
    const int h_offset = (bidx * num_panels + panel) * NUM_Q;

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<double> value = {value_expression};
        const double weighted_phi0 = weights[panel_offset + q] * phi[q];
        const double weighted_phi1 = weights[panel_offset + q] * phi[NUM_Q + q];
        local0 += value * weighted_phi0;
        local1 += value * weighted_phi1;
    }}

    __shared__ complex<double> shared0[THREADS];
    __shared__ complex<double> shared1[THREADS];
    shared0[tid] = local0;
    shared1[tid] = local1;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared0[tid] += shared0[tid + stride];
            shared1[tid] += shared1[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        const int node_offset = panel * 2;
        const int rhs_offset0 = bidx * num_dofs + panel_nodes[node_offset + 0];
        const int rhs_offset1 = bidx * num_dofs + panel_nodes[node_offset + 1];
        atomicAdd(&rhs_real[rhs_offset0], shared0[0].real());
        atomicAdd(&rhs_imag[rhs_offset0], shared0[0].imag());
        atomicAdd(&rhs_real[rhs_offset1], shared1[0].real());
        atomicAdd(&rhs_imag[rhs_offset1], shared1[0].imag());
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._projection_pair_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._projection_pair_kernels[cache_key]

    def get_projection_pair_complex_dual_kernel(self, num_quadrature: int) -> tuple[object, int]:
        variant = "fp32" if self.use_fp32_complex_rhs_kernels() else self._complex_precision
        cache_key = (int(num_quadrature), variant)
        if cache_key not in self._projection_pair_complex_dual_kernels:
            threads = 128
            kernel_name = f"project_boundary_complex_dual_{num_quadrature}"
            if variant == "fp32":
                source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

{COMPLEX64_REGULAR_HANKEL_ORDERS01_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const float* distances,
    const float* weights,
    const float* phi,
    const float* factors,
    const complex<float>* source_strengths,
    const complex<float>* wavenumbers,
    const int* panel_nodes,
    const int num_panels,
    const int num_point_batches,
    const int num_dofs,
    float* dirichlet_rhs_real,
    float* dirichlet_rhs_imag,
    float* neumann_rhs_real,
    float* neumann_rhs_imag)
{{
    const int panel = blockIdx.x;
    const int bidx = blockIdx.y;
    const int tid = threadIdx.x;
    if (panel >= num_panels) {{
        return;
    }}

    complex<float> dirichlet0(0.0f, 0.0f), dirichlet1(0.0f, 0.0f);
    complex<float> neumann0(0.0f, 0.0f), neumann1(0.0f, 0.0f);
    const int panel_offset = panel * NUM_Q;
    const int geom_batch = bidx % num_point_batches;
    const int geom_offset = (geom_batch * num_panels + panel) * NUM_Q;
    const int freq_idx = bidx / num_point_batches;
    const complex<float> source_strength = source_strengths[bidx];
    const complex<float> wavenumber = wavenumbers[freq_idx];
    const complex<float> neumann_scale = source_strength * (-complex<float>(0.0f, 0.25f) * wavenumber);

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<float> argument = wavenumber * distances[geom_offset + q];
        complex<float> h0, h1;
        hankel_orders01_complex(argument, h0, h1);
        const complex<float> dirichlet_value =
            source_strength * complex<float>(0.0f, 0.25f) * h0;
        const complex<float> neumann_value =
            neumann_scale * h1 * factors[geom_offset + q];
        const float weighted_phi0 = weights[panel_offset + q] * phi[q];
        const float weighted_phi1 = weights[panel_offset + q] * phi[NUM_Q + q];
        dirichlet0 += dirichlet_value * weighted_phi0;
        dirichlet1 += dirichlet_value * weighted_phi1;
        neumann0 += neumann_value * weighted_phi0;
        neumann1 += neumann_value * weighted_phi1;
    }}

    __shared__ complex<float> shared_dirichlet0[THREADS];
    __shared__ complex<float> shared_dirichlet1[THREADS];
    __shared__ complex<float> shared_neumann0[THREADS];
    __shared__ complex<float> shared_neumann1[THREADS];
    shared_dirichlet0[tid] = dirichlet0;
    shared_dirichlet1[tid] = dirichlet1;
    shared_neumann0[tid] = neumann0;
    shared_neumann1[tid] = neumann1;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_dirichlet0[tid] += shared_dirichlet0[tid + stride];
            shared_dirichlet1[tid] += shared_dirichlet1[tid + stride];
            shared_neumann0[tid] += shared_neumann0[tid + stride];
            shared_neumann1[tid] += shared_neumann1[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        const int node_offset = panel * 2;
        const int rhs_offset0 = bidx * num_dofs + panel_nodes[node_offset + 0];
        const int rhs_offset1 = bidx * num_dofs + panel_nodes[node_offset + 1];
        atomicAdd(&dirichlet_rhs_real[rhs_offset0], shared_dirichlet0[0].real());
        atomicAdd(&dirichlet_rhs_imag[rhs_offset0], shared_dirichlet0[0].imag());
        atomicAdd(&dirichlet_rhs_real[rhs_offset1], shared_dirichlet1[0].real());
        atomicAdd(&dirichlet_rhs_imag[rhs_offset1], shared_dirichlet1[0].imag());
        atomicAdd(&neumann_rhs_real[rhs_offset0], shared_neumann0[0].real());
        atomicAdd(&neumann_rhs_imag[rhs_offset0], shared_neumann0[0].imag());
        atomicAdd(&neumann_rhs_real[rhs_offset1], shared_neumann1[0].real());
        atomicAdd(&neumann_rhs_imag[rhs_offset1], shared_neumann1[0].imag());
    }}
}}
"""
            else:
                source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

{COMPLEX_HANKEL_ORDERS01_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const double* weights,
    const double* phi,
    const double* factors,
    const complex<double>* source_strengths,
    const complex<double>* wavenumbers,
    const int* panel_nodes,
    const int num_panels,
    const int num_point_batches,
    const int num_dofs,
    double* dirichlet_rhs_real,
    double* dirichlet_rhs_imag,
    double* neumann_rhs_real,
    double* neumann_rhs_imag)
{{
    const int panel = blockIdx.x;
    const int bidx = blockIdx.y;
    const int tid = threadIdx.x;
    if (panel >= num_panels) {{
        return;
    }}

    complex<double> dirichlet0(0.0, 0.0), dirichlet1(0.0, 0.0);
    complex<double> neumann0(0.0, 0.0), neumann1(0.0, 0.0);
    const int panel_offset = panel * NUM_Q;
    const int geom_batch = bidx % num_point_batches;
    const int geom_offset = (geom_batch * num_panels + panel) * NUM_Q;
    const int freq_idx = bidx / num_point_batches;
    const complex<double> source_strength = source_strengths[bidx];
    const complex<double> wavenumber = wavenumbers[freq_idx];
    const complex<double> neumann_scale = source_strength * (-complex<double>(0.0, 0.25) * wavenumber);

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<double> argument = wavenumber * distances[geom_offset + q];
        complex<double> h0, h1;
        hankel_orders01_complex(argument, h0, h1);
        const complex<double> dirichlet_value =
            source_strength * complex<double>(0.0, 0.25) * h0;
        const complex<double> neumann_value =
            neumann_scale * h1 * factors[geom_offset + q];
        const double weighted_phi0 = weights[panel_offset + q] * phi[q];
        const double weighted_phi1 = weights[panel_offset + q] * phi[NUM_Q + q];
        dirichlet0 += dirichlet_value * weighted_phi0;
        dirichlet1 += dirichlet_value * weighted_phi1;
        neumann0 += neumann_value * weighted_phi0;
        neumann1 += neumann_value * weighted_phi1;
    }}

    __shared__ complex<double> shared_dirichlet0[THREADS];
    __shared__ complex<double> shared_dirichlet1[THREADS];
    __shared__ complex<double> shared_neumann0[THREADS];
    __shared__ complex<double> shared_neumann1[THREADS];
    shared_dirichlet0[tid] = dirichlet0;
    shared_dirichlet1[tid] = dirichlet1;
    shared_neumann0[tid] = neumann0;
    shared_neumann1[tid] = neumann1;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_dirichlet0[tid] += shared_dirichlet0[tid + stride];
            shared_dirichlet1[tid] += shared_dirichlet1[tid + stride];
            shared_neumann0[tid] += shared_neumann0[tid + stride];
            shared_neumann1[tid] += shared_neumann1[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        const int node_offset = panel * 2;
        const int rhs_offset0 = bidx * num_dofs + panel_nodes[node_offset + 0];
        const int rhs_offset1 = bidx * num_dofs + panel_nodes[node_offset + 1];
        atomicAdd(&dirichlet_rhs_real[rhs_offset0], shared_dirichlet0[0].real());
        atomicAdd(&dirichlet_rhs_imag[rhs_offset0], shared_dirichlet0[0].imag());
        atomicAdd(&dirichlet_rhs_real[rhs_offset1], shared_dirichlet1[0].real());
        atomicAdd(&dirichlet_rhs_imag[rhs_offset1], shared_dirichlet1[0].imag());
        atomicAdd(&neumann_rhs_real[rhs_offset0], shared_neumann0[0].real());
        atomicAdd(&neumann_rhs_imag[rhs_offset0], shared_neumann0[0].imag());
        atomicAdd(&neumann_rhs_real[rhs_offset1], shared_neumann1[0].real());
        atomicAdd(&neumann_rhs_imag[rhs_offset1], shared_neumann1[0].imag());
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._projection_pair_complex_dual_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._projection_pair_complex_dual_kernels[cache_key]

    def get_projection_pair_dual_kernel(self, num_quadrature: int) -> tuple[object, int]:
        cache_key = int(num_quadrature)
        if cache_key not in self._projection_pair_dual_kernels:
            threads = 128
            kernel_name = f"project_boundary_dual_{num_quadrature}"
            source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const double* weights,
    const double* phi,
    const double* factors,
    const complex<double>* source_strengths,
    const int* panel_nodes,
    const double* real_wavenumbers,
    const int num_panels,
    const int num_point_batches,
    const int num_dofs,
    double* dirichlet_rhs_real,
    double* dirichlet_rhs_imag,
    double* neumann_rhs_real,
    double* neumann_rhs_imag)
{{
    const int panel = blockIdx.x;
    const int bidx = blockIdx.y;
    const int tid = threadIdx.x;
    if (panel >= num_panels) {{
        return;
    }}

    complex<double> dirichlet0(0.0, 0.0), dirichlet1(0.0, 0.0);
    complex<double> neumann0(0.0, 0.0), neumann1(0.0, 0.0);
    const int panel_offset = panel * NUM_Q;
    const int geom_batch = bidx % num_point_batches;
    const int geom_offset = (geom_batch * num_panels + panel) * NUM_Q;
    const double real_wavenumber = real_wavenumbers[bidx];

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const double argument = real_wavenumber * distances[geom_offset + q];
        const complex<double> h0(j0(argument), y0(argument));
        const complex<double> h1(j1(argument), y1(argument));
        const complex<double> dirichlet_value =
            source_strengths[bidx] * complex<double>(0.0, 0.25) * h0;
        const complex<double> neumann_value =
            source_strengths[bidx]
            * complex<double>(0.0, -0.25 * real_wavenumber)
            * h1
            * factors[geom_offset + q];
        const double weighted_phi0 = weights[panel_offset + q] * phi[q];
        const double weighted_phi1 = weights[panel_offset + q] * phi[NUM_Q + q];
        dirichlet0 += dirichlet_value * weighted_phi0;
        dirichlet1 += dirichlet_value * weighted_phi1;
        neumann0 += neumann_value * weighted_phi0;
        neumann1 += neumann_value * weighted_phi1;
    }}

    __shared__ complex<double> shared_dirichlet0[THREADS];
    __shared__ complex<double> shared_dirichlet1[THREADS];
    __shared__ complex<double> shared_neumann0[THREADS];
    __shared__ complex<double> shared_neumann1[THREADS];
    shared_dirichlet0[tid] = dirichlet0;
    shared_dirichlet1[tid] = dirichlet1;
    shared_neumann0[tid] = neumann0;
    shared_neumann1[tid] = neumann1;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_dirichlet0[tid] += shared_dirichlet0[tid + stride];
            shared_dirichlet1[tid] += shared_dirichlet1[tid + stride];
            shared_neumann0[tid] += shared_neumann0[tid + stride];
            shared_neumann1[tid] += shared_neumann1[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        const int node_offset = panel * 2;
        const int rhs_offset0 = bidx * num_dofs + panel_nodes[node_offset + 0];
        const int rhs_offset1 = bidx * num_dofs + panel_nodes[node_offset + 1];
        atomicAdd(&dirichlet_rhs_real[rhs_offset0], shared_dirichlet0[0].real());
        atomicAdd(&dirichlet_rhs_imag[rhs_offset0], shared_dirichlet0[0].imag());
        atomicAdd(&dirichlet_rhs_real[rhs_offset1], shared_dirichlet1[0].real());
        atomicAdd(&dirichlet_rhs_imag[rhs_offset1], shared_dirichlet1[0].imag());
        atomicAdd(&neumann_rhs_real[rhs_offset0], shared_neumann0[0].real());
        atomicAdd(&neumann_rhs_imag[rhs_offset0], shared_neumann0[0].imag());
        atomicAdd(&neumann_rhs_real[rhs_offset1], shared_neumann1[0].real());
        atomicAdd(&neumann_rhs_imag[rhs_offset1], shared_neumann1[0].imag());
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._projection_pair_dual_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._projection_pair_dual_kernels[cache_key]

    def get_potential_pair_kernel(self, kind: str, num_quadrature: int) -> tuple[object, int]:
        cache_key = (kind, int(num_quadrature))
        if cache_key not in self._potential_pair_kernels:
            threads = 128
            kernel_name = f"evaluate_potential_pair_{sanitize_identifier(kind)}_{num_quadrature}"
            if kind == "single":
                value_expression = "complex<double>(0.0, 0.25) * h_values[h_offset + q]"
            elif kind == "double":
                value_expression = (
                    "(complex<double>(0.0, 0.25) * wavenumber) "
                    "* h_values[h_offset + q] * factors[geom_offset + q]"
                )
            else:
                raise ValueError(f"Unsupported potential kernel kind: {kind}")

            source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

extern "C" __global__ void {kernel_name}(
    const complex<double>* h_values,
    const double* weights,
    const double* phi,
    const int* panel_nodes,
    const double* factors,
    const complex<double>* density,
    const complex<double> wavenumber,
    const int num_panels,
    const int num_point_batches,
    const int num_dofs,
    double* out_real,
    double* out_imag)
{{
    const int panel = blockIdx.x;
    const int bidx = blockIdx.y;
    const int tid = threadIdx.x;
    if (panel >= num_panels) {{
        return;
    }}

    complex<double> local_sum(0.0, 0.0);
    const int panel_offset = panel * NUM_Q;
    const int geom_batch = bidx % num_point_batches;
    const int geom_offset = (geom_batch * num_panels + panel) * NUM_Q;
    const int h_offset = (bidx * num_panels + panel) * NUM_Q;
    const int node_offset = panel * 2;
    const complex<double> density0 = density[bidx * num_dofs + panel_nodes[node_offset + 0]];
    const complex<double> density1 = density[bidx * num_dofs + panel_nodes[node_offset + 1]];

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<double> density_value = density0 * phi[q] + density1 * phi[NUM_Q + q];
        const complex<double> kernel_value = {value_expression};
        local_sum += weights[panel_offset + q] * kernel_value * density_value;
    }}

    __shared__ complex<double> shared_sum[THREADS];
    shared_sum[tid] = local_sum;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_sum[tid] += shared_sum[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        atomicAdd(&out_real[bidx], shared_sum[0].real());
        atomicAdd(&out_imag[bidx], shared_sum[0].imag());
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._potential_pair_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._potential_pair_kernels[cache_key]

    def get_potential_pair_dual_kernel(self, num_quadrature: int) -> tuple[object, int]:
        cache_key = int(num_quadrature)
        if cache_key not in self._potential_pair_dual_kernels:
            threads = 128
            kernel_name = f"evaluate_potential_pair_dual_{num_quadrature}"
            source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const double* weights,
    const double* phi,
    const int* panel_nodes,
    const double* factors,
    const complex<double>* single_density,
    const complex<double>* double_density,
    const double* real_wavenumbers,
    const int num_panels,
    const int num_point_batches,
    const int num_dofs,
    double* single_out_real,
    double* single_out_imag,
    double* double_out_real,
    double* double_out_imag)
{{
    const int panel = blockIdx.x;
    const int bidx = blockIdx.y;
    const int tid = threadIdx.x;
    if (panel >= num_panels) {{
        return;
    }}

    complex<double> single_sum(0.0, 0.0);
    complex<double> double_sum(0.0, 0.0);
    const int panel_offset = panel * NUM_Q;
    const int geom_batch = bidx % num_point_batches;
    const int geom_offset = (geom_batch * num_panels + panel) * NUM_Q;
    const int node_offset = panel * 2;
    const complex<double> single_density0 = single_density[bidx * num_dofs + panel_nodes[node_offset + 0]];
    const complex<double> single_density1 = single_density[bidx * num_dofs + panel_nodes[node_offset + 1]];
    const complex<double> double_density0 = double_density[bidx * num_dofs + panel_nodes[node_offset + 0]];
    const complex<double> double_density1 = double_density[bidx * num_dofs + panel_nodes[node_offset + 1]];
    const double real_wavenumber = real_wavenumbers[bidx];

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const double argument = real_wavenumber * distances[geom_offset + q];
        const complex<double> h0(j0(argument), y0(argument));
        const complex<double> h1(j1(argument), y1(argument));
        const complex<double> single_density_value =
            single_density0 * phi[q] + single_density1 * phi[NUM_Q + q];
        const complex<double> double_density_value =
            double_density0 * phi[q] + double_density1 * phi[NUM_Q + q];
        const complex<double> single_kernel_value =
            complex<double>(0.0, 0.25) * h0;
        const complex<double> double_kernel_value =
            complex<double>(0.0, 0.25 * real_wavenumber)
            * h1
            * factors[geom_offset + q];
        const double weighted = weights[panel_offset + q];
        single_sum += weighted * single_kernel_value * single_density_value;
        double_sum += weighted * double_kernel_value * double_density_value;
    }}

    __shared__ complex<double> shared_single[THREADS];
    __shared__ complex<double> shared_double[THREADS];
    shared_single[tid] = single_sum;
    shared_double[tid] = double_sum;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_single[tid] += shared_single[tid + stride];
            shared_double[tid] += shared_double[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        atomicAdd(&single_out_real[bidx], shared_single[0].real());
        atomicAdd(&single_out_imag[bidx], shared_single[0].imag());
        atomicAdd(&double_out_real[bidx], shared_double[0].real());
        atomicAdd(&double_out_imag[bidx], shared_double[0].imag());
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._potential_pair_dual_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._potential_pair_dual_kernels[cache_key]

    def get_potential_pair_complex_dual_kernel(self, num_quadrature: int) -> tuple[object, int]:
        variant = "fp32" if self.use_fp32_complex_rhs_kernels() else self._complex_precision
        cache_key = (int(num_quadrature), variant)
        if cache_key not in self._potential_pair_complex_dual_kernels:
            threads = 128
            kernel_name = f"evaluate_potential_pair_complex_dual_{num_quadrature}"
            if variant == "fp32":
                source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

{COMPLEX64_REGULAR_HANKEL_ORDERS01_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const float* distances,
    const float* weights,
    const float* phi,
    const int* panel_nodes,
    const float* factors,
    const complex<float>* single_density,
    const complex<float>* double_density,
    const complex<float>* wavenumbers,
    const int num_panels,
    const int num_point_batches,
    const int num_dofs,
    float* single_out_real,
    float* single_out_imag,
    float* double_out_real,
    float* double_out_imag)
{{
    const int panel = blockIdx.x;
    const int bidx = blockIdx.y;
    const int tid = threadIdx.x;
    if (panel >= num_panels) {{
        return;
    }}

    complex<float> single_sum(0.0f, 0.0f);
    complex<float> double_sum(0.0f, 0.0f);
    const int panel_offset = panel * NUM_Q;
    const int geom_batch = bidx % num_point_batches;
    const int geom_offset = (geom_batch * num_panels + panel) * NUM_Q;
    const int node_offset = panel * 2;
    const int freq_idx = bidx / num_point_batches;
    const complex<float> single_density0 = single_density[bidx * num_dofs + panel_nodes[node_offset + 0]];
    const complex<float> single_density1 = single_density[bidx * num_dofs + panel_nodes[node_offset + 1]];
    const complex<float> double_density0 = double_density[bidx * num_dofs + panel_nodes[node_offset + 0]];
    const complex<float> double_density1 = double_density[bidx * num_dofs + panel_nodes[node_offset + 1]];
    const complex<float> wavenumber = wavenumbers[freq_idx];
    const complex<float> double_scale = complex<float>(0.0f, 0.25f) * wavenumber;

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<float> argument = wavenumber * distances[geom_offset + q];
        complex<float> h0, h1;
        hankel_orders01_complex(argument, h0, h1);
        const complex<float> single_density_value =
            single_density0 * phi[q] + single_density1 * phi[NUM_Q + q];
        const complex<float> double_density_value =
            double_density0 * phi[q] + double_density1 * phi[NUM_Q + q];
        const complex<float> single_kernel_value =
            complex<float>(0.0f, 0.25f) * h0;
        const complex<float> double_kernel_value =
            double_scale * h1 * factors[geom_offset + q];
        const float weighted = weights[panel_offset + q];
        single_sum += weighted * single_kernel_value * single_density_value;
        double_sum += weighted * double_kernel_value * double_density_value;
    }}

    __shared__ complex<float> shared_single[THREADS];
    __shared__ complex<float> shared_double[THREADS];
    shared_single[tid] = single_sum;
    shared_double[tid] = double_sum;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_single[tid] += shared_single[tid + stride];
            shared_double[tid] += shared_double[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        atomicAdd(&single_out_real[bidx], shared_single[0].real());
        atomicAdd(&single_out_imag[bidx], shared_single[0].imag());
        atomicAdd(&double_out_real[bidx], shared_double[0].real());
        atomicAdd(&double_out_imag[bidx], shared_double[0].imag());
    }}
}}
"""
            else:
                source = f"""
#include <cupy/complex.cuh>

#define NUM_Q {num_quadrature}
#define THREADS {threads}

{COMPLEX_HANKEL_ORDERS01_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const double* weights,
    const double* phi,
    const int* panel_nodes,
    const double* factors,
    const complex<double>* single_density,
    const complex<double>* double_density,
    const complex<double>* wavenumbers,
    const int num_panels,
    const int num_point_batches,
    const int num_dofs,
    double* single_out_real,
    double* single_out_imag,
    double* double_out_real,
    double* double_out_imag)
{{
    const int panel = blockIdx.x;
    const int bidx = blockIdx.y;
    const int tid = threadIdx.x;
    if (panel >= num_panels) {{
        return;
    }}

    complex<double> single_sum(0.0, 0.0);
    complex<double> double_sum(0.0, 0.0);
    const int panel_offset = panel * NUM_Q;
    const int geom_batch = bidx % num_point_batches;
    const int geom_offset = (geom_batch * num_panels + panel) * NUM_Q;
    const int node_offset = panel * 2;
    const int freq_idx = bidx / num_point_batches;
    const complex<double> single_density0 = single_density[bidx * num_dofs + panel_nodes[node_offset + 0]];
    const complex<double> single_density1 = single_density[bidx * num_dofs + panel_nodes[node_offset + 1]];
    const complex<double> double_density0 = double_density[bidx * num_dofs + panel_nodes[node_offset + 0]];
    const complex<double> double_density1 = double_density[bidx * num_dofs + panel_nodes[node_offset + 1]];
    const complex<double> wavenumber = wavenumbers[freq_idx];
    const complex<double> double_scale = complex<double>(0.0, 0.25) * wavenumber;

    for (int q = tid; q < NUM_Q; q += THREADS) {{
        const complex<double> argument = wavenumber * distances[geom_offset + q];
        complex<double> h0, h1;
        hankel_orders01_complex(argument, h0, h1);
        const complex<double> single_density_value =
            single_density0 * phi[q] + single_density1 * phi[NUM_Q + q];
        const complex<double> double_density_value =
            double_density0 * phi[q] + double_density1 * phi[NUM_Q + q];
        const complex<double> single_kernel_value =
            complex<double>(0.0, 0.25) * h0;
        const complex<double> double_kernel_value =
            double_scale * h1 * factors[geom_offset + q];
        const double weighted = weights[panel_offset + q];
        single_sum += weighted * single_kernel_value * single_density_value;
        double_sum += weighted * double_kernel_value * double_density_value;
    }}

    __shared__ complex<double> shared_single[THREADS];
    __shared__ complex<double> shared_double[THREADS];
    shared_single[tid] = single_sum;
    shared_double[tid] = double_sum;
    __syncthreads();

    for (int stride = THREADS / 2; stride > 0; stride >>= 1) {{
        if (tid < stride) {{
            shared_single[tid] += shared_single[tid + stride];
            shared_double[tid] += shared_double[tid + stride];
        }}
        __syncthreads();
    }}

    if (tid == 0) {{
        atomicAdd(&single_out_real[bidx], shared_single[0].real());
        atomicAdd(&single_out_imag[bidx], shared_single[0].imag());
        atomicAdd(&double_out_real[bidx], shared_double[0].real());
        atomicAdd(&double_out_imag[bidx], shared_double[0].imag());
    }}
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._potential_pair_complex_dual_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._potential_pair_complex_dual_kernels[cache_key]

    def get_incident_receiver_complex_kernel(self) -> tuple[object, int]:
        variant = "fp32" if self.use_fp32_complex_rhs_kernels() else self._complex_precision
        cache_key = f"incident_receiver_complex_{variant}"
        if cache_key not in self._incident_receiver_complex_kernels:
            threads = 128
            kernel_name = "evaluate_incident_receiver_complex"
            if variant == "fp32":
                source = f"""
#include <cupy/complex.cuh>

#define THREADS {threads}

{COMPLEX64_REGULAR_HANKEL_ORDERS01_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const float* distances,
    const complex<float>* source_strengths,
    const complex<float>* wavenumbers,
    const int num_point_batches,
    const long total_batches,
    complex<float>* out)
{{
    const long bidx = static_cast<long>(blockIdx.x) * THREADS + threadIdx.x;
    if (bidx >= total_batches) {{
        return;
    }}

    const int geom_idx = static_cast<int>(bidx % num_point_batches);
    const int freq_idx = static_cast<int>(bidx / num_point_batches);
    const complex<float> argument = wavenumbers[freq_idx] * distances[geom_idx];
    complex<float> h0, h1;
    hankel_orders01_complex(argument, h0, h1);
    out[bidx] = source_strengths[bidx] * complex<float>(0.0f, 0.25f) * h0;
}}
"""
            else:
                source = f"""
#include <cupy/complex.cuh>

#define THREADS {threads}

{COMPLEX_HANKEL_ORDERS01_DEVICE_HELPERS}

extern "C" __global__ void {kernel_name}(
    const double* distances,
    const complex<double>* source_strengths,
    const complex<double>* wavenumbers,
    const int num_point_batches,
    const long total_batches,
    complex<double>* out)
{{
    const long bidx = static_cast<long>(blockIdx.x) * THREADS + threadIdx.x;
    if (bidx >= total_batches) {{
        return;
    }}

    const int geom_idx = static_cast<int>(bidx % num_point_batches);
    const int freq_idx = static_cast<int>(bidx / num_point_batches);
    const complex<double> argument = wavenumbers[freq_idx] * distances[geom_idx];
    complex<double> h0, h1;
    hankel_orders01_complex(argument, h0, h1);
    out[bidx] = source_strengths[bidx] * complex<double>(0.0, 0.25) * h0;
}}
"""
            module = self._build_module(source, (kernel_name,))
            self._incident_receiver_complex_kernels[cache_key] = (module.get_function(kernel_name), threads)
        return self._incident_receiver_complex_kernels[cache_key]
