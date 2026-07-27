from __future__ import annotations

import numpy as np


def rts_smooth(F, x_filt, P_filt, x_pred, P_pred):
    """
    Rauch-Tung-Striebel (RTS) backward smoother.

    Improves the forward Kalman trajectory by using future information.

    Forward Kalman filter:
        frame N only knows previous frames.

    RTS smoother:
        frame N can also use future frames to correct the past.

    Useful for offline football analysis because the full video is available.
    It improves ball positions during short detection gaps.
    """

    n = len(x_filt)

    # Storage for smoothed states and uncertainties.
    x_smooth = [None] * n
    P_smooth = [None] * n


    # The last frame cannot be improved because there is no future frame.
    x_smooth[-1] = x_filt[-1]
    P_smooth[-1] = P_filt[-1]


    # Go backward through the track.
    for k in range(n - 2, -1, -1):

        # Compute inverse of predicted uncertainty.
        # pinv fallback handles rare singular matrices.
        try:
            P_pred_inv = np.linalg.inv(P_pred[k + 1])
        except np.linalg.LinAlgError:
            P_pred_inv = np.linalg.pinv(P_pred[k + 1])


        # RTS smoothing gain:
        # decides how much future information should correct
        # the current forward estimate.
        C = (
            P_filt[k]
            @ F.T
            @ P_pred_inv
        )


        # Correct the state using the difference between:
        # - smoothed future estimate
        # - forward prediction
        x_smooth[k] = (
            x_filt[k]
            + C @ (x_smooth[k + 1] - x_pred[k + 1])
        )


        # Update uncertainty after smoothing.
        P_smooth[k] = (
            P_filt[k]
            + C
            @ (P_smooth[k + 1] - P_pred[k + 1])
            @ C.T
        )


    return x_smooth, P_smooth