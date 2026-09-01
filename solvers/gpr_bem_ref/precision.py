"""Shared precision-policy helpers for TMz BEM backends and kernels."""

from __future__ import annotations

ALLOWED_PRECISION_POLICIES = (
    "stable",
    "auto",
    "fp32_regular",
    "fp32_regular_near",
    "fp32_regular_near_adjacent",
)

ALLOWED_LEGACY_COMPLEX_KERNEL_POLICIES = (
    "off",
    "regular",
    "regular_near",
    "regular_near_adjacent",
)


def normalize_legacy_complex_kernel_policy(
    experimental_fp32_complex_regular_kernel: bool,
    experimental_fp32_complex_kernel_policy: str,
) -> str:
    normalized_policy = experimental_fp32_complex_kernel_policy.strip().lower()
    if normalized_policy == "off" and experimental_fp32_complex_regular_kernel:
        normalized_policy = "regular"
    if normalized_policy not in ALLOWED_LEGACY_COMPLEX_KERNEL_POLICIES:
        raise ValueError(
            "experimental_fp32_complex_kernel_policy must be one of: "
            "'off', 'regular', 'regular_near', 'regular_near_adjacent'."
        )
    return normalized_policy


def resolve_precision_policy(
    precision_policy: str,
    *,
    complex_precision: str,
    backend_name: str,
    experimental_fp32_complex_regular_kernel: bool = False,
    experimental_fp32_complex_kernel_policy: str = "off",
) -> tuple[str, str, str]:
    normalized_precision_policy = precision_policy.strip().lower()
    if normalized_precision_policy not in ALLOWED_PRECISION_POLICIES:
        raise ValueError(
            "precision_policy must be one of: "
            "'stable', 'auto', 'fp32_regular', 'fp32_regular_near', "
            "'fp32_regular_near_adjacent'."
        )

    normalized_legacy_policy = normalize_legacy_complex_kernel_policy(
        experimental_fp32_complex_regular_kernel,
        experimental_fp32_complex_kernel_policy,
    )

    normalized_complex_precision = complex_precision.strip().lower()
    if normalized_precision_policy == "stable":
        resolved_policy = normalized_legacy_policy
    elif normalized_precision_policy == "auto":
        resolved_policy = (
            "regular_near_adjacent"
            if backend_name == "cupy" and normalized_complex_precision == "complex128"
            else "off"
        )
    elif normalized_precision_policy == "fp32_regular":
        resolved_policy = "regular"
    elif normalized_precision_policy == "fp32_regular_near":
        resolved_policy = "regular_near"
    else:
        resolved_policy = "regular_near_adjacent"

    return normalized_precision_policy, normalized_legacy_policy, resolved_policy
