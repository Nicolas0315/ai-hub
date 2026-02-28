"""
KS33b #5: Session Guardian — time-based reset with user confirmation.

Monitors ephemeral learning session duration and verification count.
When thresholds are reached, generates a reset recommendation.

Does NOT auto-reset — returns a prompt for the caller to present to the user.
"""

import time


class SessionGuardian:
    """Monitors ephemeral session and recommends reset when needed."""
    
    # Configurable thresholds
    DEFAULT_TIME_LIMIT = 3600      # 1 hour
    DEFAULT_VERIFY_LIMIT = 50      # 50 verifications
    DEFAULT_WARN_RATIO = 0.8       # Warn at 80% of limit
    
    def __init__(self, session, time_limit=None, verify_limit=None):
        self.session = session
        self.time_limit = time_limit or self.DEFAULT_TIME_LIMIT
        self.verify_limit = verify_limit or self.DEFAULT_VERIFY_LIMIT
        self._warned = False
        self._reset_requested = False
    
    def check(self):
        """Check session health. Returns status dict.
        
        If reset is recommended, includes a confirmation prompt.
        """
        status = self.session.get_status()
        age = status["session_age_seconds"]
        count = status["verification_count"]
        
        time_ratio = age / self.time_limit
        verify_ratio = count / self.verify_limit
        
        result = {
            "age_seconds": round(age, 1),
            "age_minutes": round(age / 60, 1),
            "verification_count": count,
            "time_ratio": round(time_ratio, 3),
            "verify_ratio": round(verify_ratio, 3),
            "status": "healthy",
            "reset_recommended": False,
            "prompt": None,
        }
        
        # Check if limits exceeded
        if time_ratio >= 1.0 or verify_ratio >= 1.0:
            result["status"] = "reset_recommended"
            result["reset_recommended"] = True
            
            reasons = []
            if time_ratio >= 1.0:
                reasons.append(f"セッション時間が{round(age/60)}分に達しました（上限: {self.time_limit//60}分）")
            if verify_ratio >= 1.0:
                reasons.append(f"検証回数が{count}回に達しました（上限: {self.verify_limit}回）")
            
            result["prompt"] = (
                "⚠️ セッションモードがオンのままです。\n"
                f"{'、'.join(reasons)}。\n"
                "長時間のセッションは学習が蓄積的に振る舞うリスクがあります。\n"
                "そろそろセッションのリセットを行いますか？\n"
                "\n"
                "→ リセットする: ks.reset_learning()\n"
                "→ 延長する: guardian.extend(minutes=30)\n"
                "→ 無視する: guardian.dismiss()"
            )
        
        elif time_ratio >= self.DEFAULT_WARN_RATIO or verify_ratio >= self.DEFAULT_WARN_RATIO:
            result["status"] = "warning"
            if not self._warned:
                self._warned = True
                remaining_time = max(0, self.time_limit - age)
                remaining_verify = max(0, self.verify_limit - count)
                result["prompt"] = (
                    f"ℹ️ セッション残り: {round(remaining_time/60)}分 / {remaining_verify}検証回。"
                )
        
        return result
    
    def extend(self, minutes=30):
        """Extend session limits."""
        self.time_limit += minutes * 60
        self._warned = False
        return {"extended_by_minutes": minutes, "new_time_limit": self.time_limit}
    
    def dismiss(self):
        """Dismiss reset recommendation (user chose to continue)."""
        self._reset_requested = False
        self._warned = False
        # Extend by 50%
        self.time_limit = int(self.time_limit * 1.5)
        self.verify_limit = int(self.verify_limit * 1.5)
        return {"dismissed": True, "new_limits": {
            "time": self.time_limit,
            "verify": self.verify_limit,
        }}
