"""Metrics used for the paper tables (including SingleTX's SSIM convention)."""

from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F


def snr_db(reconstruction: np.ndarray, truth: np.ndarray) -> float:
    """Contrast-image SNR in dB, as used for the paper comparison."""
    recon = np.asarray(reconstruction, dtype=np.float64)
    gt = np.asarray(truth, dtype=np.float64)
    err = np.linalg.norm((recon - gt).reshape(-1))
    truth_norm = max(float(np.linalg.norm(gt.reshape(-1))), 1e-12)
    return float(20.0 * np.log10(truth_norm / max(float(err), 1e-12)))


def single_tx_metrics(epsilon_pred: np.ndarray, epsilon_gt: np.ndarray) -> dict[str, float]:
    """RRMSE, PSNR, and SSIM on absolute relative permittivity."""
    pred = np.asarray(epsilon_pred, dtype=np.float64).reshape(1, -1)
    gt = np.asarray(epsilon_gt, dtype=np.float64).reshape(1, -1)
    side = int(np.asarray(epsilon_gt).shape[-1])
    gt_safe = np.where(np.abs(gt) > 1e-12, gt, 1e-12)
    rrmse = np.sqrt(np.sum(((pred - gt) / gt_safe) ** 2, axis=-1) / (side * side))
    max_gt = np.max(gt, axis=-1)
    mse = np.mean((pred - gt) ** 2, axis=-1)
    psnr = -10.0 * np.log(np.maximum(mse, 1e-30) / np.maximum(max_gt**2, 1e-30)) / np.log(10.0)
    return {
        "rrmse": float(np.mean(rrmse)),
        "psnr": float(np.mean(psnr)),
        "ssim": single_tx_ssim(epsilon_pred, epsilon_gt),
    }


def single_tx_ssim(epsilon_pred: np.ndarray, epsilon_gt: np.ndarray) -> float:
    """Match SingleTX's 11x11, sigma=1.5, zero-padded PyTorch SSIM."""
    gt = np.asarray(epsilon_gt, dtype=np.float64)
    pred = np.asarray(epsilon_pred, dtype=np.float64)
    gt = gt / max(float(np.max(gt)), 1e-12)
    pred = pred / max(float(np.max(pred)), 1e-12)
    gt_t = torch.as_tensor(gt.reshape(1, 1, *gt.shape), dtype=torch.float64)
    pred_t = torch.as_tensor(pred.reshape(1, 1, *pred.shape), dtype=torch.float64)
    # SingleTX builds its window in float32, then casts to the image dtype.
    x = torch.arange(11, dtype=torch.float32) - 5
    gaussian = torch.exp(-(x * x) / (2 * 1.5**2))
    gaussian = gaussian / gaussian.sum()
    window = torch.outer(gaussian, gaussian).reshape(1, 1, 11, 11).to(torch.float64)
    mu_pred = F.conv2d(pred_t, window, padding=5)
    mu_gt = F.conv2d(gt_t, window, padding=5)
    pred_sq = mu_pred.square()
    gt_sq = mu_gt.square()
    pred_gt = mu_pred * mu_gt
    var_pred = F.conv2d(pred_t.square(), window, padding=5) - pred_sq
    var_gt = F.conv2d(gt_t.square(), window, padding=5) - gt_sq
    cov = F.conv2d(pred_t * gt_t, window, padding=5) - pred_gt
    score = ((2 * pred_gt + 0.01**2) * (2 * cov + 0.03**2)) / (
        (pred_sq + gt_sq + 0.01**2) * (var_pred + var_gt + 0.03**2)
    )
    return float(score.mean())
