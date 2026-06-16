"""Pure banking calculator logic used by the MCP server and tests."""

from __future__ import annotations

import re
from typing import Any

MAX_FOIR_RATIO = 0.5
AmountInput = float | int | str


def normalize_amount(value: AmountInput) -> float:
    """Normalize rupee amounts, including Indian units such as lakh and crore."""
    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        raise ValueError("amount must be a number or string.")

    amount_text = value.strip().lower()
    amount_text = amount_text.replace("inr", "").replace("₹", "").replace("â‚¹", "")
    amount_text = amount_text.replace(",", "").replace("rs.", "").replace("rs", "").replace("₹", "").strip()
    unit_match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|crore|crores|cr|l)", amount_text)
    if unit_match:
        number = float(unit_match.group(1))
        unit = unit_match.group(2)
        if unit in {"lakh", "lakhs", "lac", "lacs", "l"}:
            return number * 100_000
        if unit in {"crore", "crores", "cr"}:
            return number * 10_000_000

    try:
        return float(amount_text)
    except ValueError as exc:
        raise ValueError(
            "amount must be a number or use Indian units such as '5 lakh' or '1 crore'."
        ) from exc


def _coerce_number(value: float | int | str) -> float:
    if isinstance(value, str):
        return float(value.strip().replace(",", "").replace("%", ""))
    return float(value)


def _format_indian_number(value: float) -> str:
    """Format a number with Indian digit grouping."""
    rounded = f"{value:.2f}"
    integer_part, decimal_part = rounded.split(".")
    sign = ""
    if integer_part.startswith("-"):
        sign = "-"
        integer_part = integer_part[1:]

    if len(integer_part) <= 3:
        grouped = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        grouped = ",".join(reversed(groups)) + "," + last_three

    return f"{sign}{grouped}.{decimal_part}"


def _format_inr(value: float) -> str:
    """Format a rupee value for calculator summaries."""
    return f"INR {_format_indian_number(value)}"


def _require_positive_number(name: str, value: float | int | str) -> float:
    try:
        number = _coerce_number(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc

    if number <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return number


def _require_positive_amount(name: str, value: AmountInput) -> float:
    try:
        amount = normalize_amount(value)
    except ValueError as exc:
        raise ValueError(f"{name} {exc}") from exc

    if amount <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return amount


def _require_non_negative_number(name: str, value: float | int | str) -> float:
    try:
        number = _coerce_number(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc

    if number < 0:
        raise ValueError(f"{name} cannot be negative.")
    return number


def calculate_emi(principal: AmountInput, annual_rate: float, tenure_years: float) -> float:
    """Calculate an estimated monthly EMI for a reducing-balance loan."""
    principal_value = _require_positive_amount("principal", principal)
    rate_value = _require_non_negative_number("annual_rate", annual_rate)
    tenure_value = _require_positive_number("tenure_years", tenure_years)

    months = int(round(tenure_value * 12))
    if months <= 0:
        raise ValueError("tenure_years must be long enough to include at least one month.")

    monthly_rate = rate_value / 100 / 12
    if monthly_rate == 0:
        return round(principal_value / months, 2)

    emi = principal_value * monthly_rate * ((1 + monthly_rate) ** months) / (((1 + monthly_rate) ** months) - 1)
    return round(emi, 2)


def check_loan_eligibility(
    monthly_income: AmountInput,
    monthly_obligations: AmountInput,
    requested_loan_amount: AmountInput,
    annual_rate: float,
    tenure_years: float,
) -> dict[str, Any]:
    """Estimate loan eligibility using EMI affordability and FOIR/DTI ratio."""
    income = _require_positive_amount("monthly_income", monthly_income)
    obligations = normalize_amount(monthly_obligations)
    if obligations < 0:
        raise ValueError("monthly_obligations cannot be negative.")
    loan_amount = _require_positive_amount("requested_loan_amount", requested_loan_amount)
    rate = _require_non_negative_number("annual_rate", annual_rate)
    tenure = _require_positive_number("tenure_years", tenure_years)

    estimated_emi = calculate_emi(loan_amount, rate, tenure)
    max_total_debt_payment = income * MAX_FOIR_RATIO
    max_affordable_emi = max(0.0, max_total_debt_payment - obligations)
    foir_ratio = (obligations + estimated_emi) / income
    eligible = estimated_emi <= max_affordable_emi

    if eligible:
        reason = "Estimated EMI is within the maximum affordable EMI at a 50% FOIR threshold."
    elif obligations >= max_total_debt_payment:
        reason = "Existing monthly obligations already meet or exceed the 50% FOIR threshold."
    else:
        reason = "Estimated EMI exceeds the maximum affordable EMI at a 50% FOIR threshold."

    return {
        "requested_loan_amount": round(loan_amount, 2),
        "monthly_income": round(income, 2),
        "monthly_obligations": round(obligations, 2),
        "eligible": eligible,
        "eligibility_status": "eligible" if eligible else "not eligible",
        "estimated_emi": round(estimated_emi, 2),
        "foir_dti_ratio": round(foir_ratio, 4),
        "foir_dti_percentage": round(foir_ratio * 100, 2),
        "max_affordable_emi": round(max_affordable_emi, 2),
        "reason": reason,
        "formatted_summary": (
            f"Eligibility status: {'eligible' if eligible else 'not eligible'}\n"
            f"Requested loan amount: {_format_inr(loan_amount)}\n"
            f"Estimated EMI: {_format_inr(estimated_emi)}\n"
            f"FOIR/DTI ratio: {foir_ratio * 100:.2f}%\n"
            f"Maximum affordable EMI: {_format_inr(max_affordable_emi)}\n"
            f"Reason: {reason}"
        ),
    }


def calculate_fd_maturity(
    principal: AmountInput,
    annual_rate: float,
    tenure_years: float,
    compounding_frequency: int = 4,
) -> dict[str, float]:
    """Calculate fixed-deposit maturity amount and interest earned."""
    principal_value = _require_positive_amount("principal", principal)
    rate_value = _require_non_negative_number("annual_rate", annual_rate)
    tenure_value = _require_positive_number("tenure_years", tenure_years)

    try:
        frequency = int(compounding_frequency)
    except (TypeError, ValueError) as exc:
        raise ValueError("compounding_frequency must be an integer.") from exc

    if frequency <= 0:
        raise ValueError("compounding_frequency must be greater than zero.")

    maturity_amount = principal_value * ((1 + (rate_value / 100) / frequency) ** (frequency * tenure_value))
    interest_earned = maturity_amount - principal_value
    return {
        "principal": round(principal_value, 2),
        "annual_rate": round(rate_value, 4),
        "tenure_years": round(tenure_value, 2),
        "compounding_frequency": frequency,
        "maturity_amount": round(maturity_amount, 2),
        "interest_earned": round(interest_earned, 2),
        "formatted_summary": (
            f"Principal: {_format_inr(principal_value)}\n"
            f"Maturity amount: {_format_inr(maturity_amount)}\n"
            f"Interest earned: {_format_inr(interest_earned)}"
        ),
    }


def compare_loan_options(options: list[dict[str, AmountInput]]) -> dict[str, Any]:
    """Compare loan options and select the one with the lowest total payment."""
    if not isinstance(options, list) or not options:
        raise ValueError("options must be a non-empty list.")

    comparison = []
    for index, option in enumerate(options, start=1):
        if not isinstance(option, dict):
            raise ValueError(f"Option {index} must be an object.")

        principal = _require_positive_amount(f"options[{index}].principal", option.get("principal"))
        annual_rate = _require_non_negative_number(f"options[{index}].annual_rate", option.get("annual_rate"))
        tenure_years = _require_positive_number(f"options[{index}].tenure_years", option.get("tenure_years"))
        months = int(round(tenure_years * 12))
        emi = calculate_emi(principal, annual_rate, tenure_years)
        total_payment = emi * months
        total_interest = total_payment - principal
        comparison.append(
            {
                "option": index,
                "principal": round(principal, 2),
                "annual_rate": round(annual_rate, 4),
                "tenure_years": round(tenure_years, 2),
                "months": months,
                "estimated_emi": round(emi, 2),
                "total_interest": round(total_interest, 2),
                "total_payment": round(total_payment, 2),
                "formatted_summary": (
                    f"Option {index}: Principal {_format_inr(principal)}, "
                    f"Rate {annual_rate:.2f}%, Tenure {tenure_years:.2f} years, "
                    f"EMI {_format_inr(emi)}, Total interest {_format_inr(total_interest)}, "
                    f"Total payment {_format_inr(total_payment)}"
                ),
            }
        )

    best_option = min(comparison, key=lambda item: item["total_payment"])
    return {
        "comparison": comparison,
        "best_option": best_option,
        "reason": "Best option is selected by the lowest estimated total payment.",
        "formatted_summary": (
            "Loan comparison:\n"
            + "\n".join(item["formatted_summary"] for item in comparison)
            + "\nBest option: "
            f"Option {best_option['option']} with total payment {_format_inr(best_option['total_payment'])}."
        ),
    }
