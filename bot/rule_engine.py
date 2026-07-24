"""
Rule Engine مینیمال نسخه‌ی اول (طبق MVP_Final_Unified.md).
فقط دو قانون:
  1. Consecutive Errors: ۳ غلط متوالی
  2. Fatigue Detection: افت ناگهانی دقت نسبت به کل جلسه

این ماژول تصمیم نمی‌گیره چه پیامی نشون داده بشه؛ فقط تشخیص می‌ده کدوم قانون
trigger شده. متن واکنش (re-teach / پیشنهاد استراحت) در handler لایه‌ی بالاتر
مشخص می‌شه (که خودش بعداً می‌تونه content-driven بشه).
"""
from dataclasses import dataclass, field
from enum import Enum

from config import CONSECUTIVE_ERROR_THRESHOLD, FATIGUE_WINDOW, FATIGUE_ACCURACY_DROP


class TriggeredRule(str, Enum):
    NONE = "none"
    CONSECUTIVE_ERRORS = "consecutive_errors"
    FATIGUE = "fatigue"


@dataclass
class QuizSession:
    """تاریخچه‌ی پاسخ‌های کاربر در طول یک جلسه (یک درس)."""
    answers: list[bool] = field(default_factory=list)  # True=درست, False=غلط
    consecutive_errors: int = 0

    def record_answer(self, is_correct: bool) -> None:
        self.answers.append(is_correct)
        if is_correct:
            self.consecutive_errors = 0
        else:
            self.consecutive_errors += 1

    def overall_accuracy(self) -> float:
        if not self.answers:
            return 1.0
        return sum(self.answers) / len(self.answers)

    def recent_accuracy(self, window: int) -> float:
        recent = self.answers[-window:]
        if not recent:
            return 1.0
        return sum(recent) / len(recent)


class RuleEngine:
    def evaluate(self, session: QuizSession) -> TriggeredRule:
        # قانون ۱: خطای متوالی (اولویت بالاتر - نشونه‌ی گپ فهمی مشخص‌تره)
        if session.consecutive_errors >= CONSECUTIVE_ERROR_THRESHOLD:
            return TriggeredRule.CONSECUTIVE_ERRORS

        # قانون ۲: خستگی (فقط وقتی داده‌ی کافی داریم که مقایسه معنادار باشه)
        if len(session.answers) >= FATIGUE_WINDOW:
            overall = session.overall_accuracy()
            recent = session.recent_accuracy(FATIGUE_WINDOW)
            if overall - recent >= FATIGUE_ACCURACY_DROP:
                return TriggeredRule.FATIGUE

        return TriggeredRule.NONE

    def reset_after_handling(self, session: QuizSession, rule: TriggeredRule) -> None:
        """بعد از اینکه واکنش به یه قانون نشون داده شد، شمارنده‌ی مربوطه رو ریست کن
        تا بلافاصله دوباره trigger نشه."""
        if rule == TriggeredRule.CONSECUTIVE_ERRORS:
            session.consecutive_errors = 0
