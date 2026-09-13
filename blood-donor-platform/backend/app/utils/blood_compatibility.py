"""
Standard ABO/Rh donor-recipient compatibility chart.

Keyed by *recipient* blood group -> list of donor blood groups that are safe
to transfuse into that recipient. Used to filter the "matching requests"
feed shown on the donor dashboard so donors mostly see requests they could
realistically help with (O- donors, being universal, show up for everyone).
"""
from app.models.user_model import BloodGroup

COMPATIBLE_DONORS_FOR_RECIPIENT: dict[str, list[str]] = {
    BloodGroup.O_NEG.value: [BloodGroup.O_NEG.value],
    BloodGroup.O_POS.value: [BloodGroup.O_NEG.value, BloodGroup.O_POS.value],
    BloodGroup.A_NEG.value: [BloodGroup.O_NEG.value, BloodGroup.A_NEG.value],
    BloodGroup.A_POS.value: [
        BloodGroup.O_NEG.value,
        BloodGroup.O_POS.value,
        BloodGroup.A_NEG.value,
        BloodGroup.A_POS.value,
    ],
    BloodGroup.B_NEG.value: [BloodGroup.O_NEG.value, BloodGroup.B_NEG.value],
    BloodGroup.B_POS.value: [
        BloodGroup.O_NEG.value,
        BloodGroup.O_POS.value,
        BloodGroup.B_NEG.value,
        BloodGroup.B_POS.value,
    ],
    BloodGroup.AB_NEG.value: [
        BloodGroup.O_NEG.value,
        BloodGroup.A_NEG.value,
        BloodGroup.B_NEG.value,
        BloodGroup.AB_NEG.value,
    ],
    BloodGroup.AB_POS.value: [bg.value for bg in BloodGroup],  # universal recipient
}


def donor_blood_groups_compatible_with(recipient_blood_group: str) -> list[str]:
    return COMPATIBLE_DONORS_FOR_RECIPIENT.get(recipient_blood_group, [])


def can_donor_help_recipient(donor_blood_group: str, recipient_blood_group: str) -> bool:
    return donor_blood_group in donor_blood_groups_compatible_with(recipient_blood_group)


def recipient_blood_groups_helpable_by_donor(donor_blood_group: str) -> list[str]:
    """Inverse of COMPATIBLE_DONORS_FOR_RECIPIENT: recipient groups this donor can help."""
    return [
        recipient_bg
        for recipient_bg, donor_list in COMPATIBLE_DONORS_FOR_RECIPIENT.items()
        if donor_blood_group in donor_list
    ]
