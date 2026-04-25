from app.services import wizard_service


def test_overlay_droplet_windows_image_uses_selected_version_label():
    source = {"id": 101, "image": {"distribution": "Debian", "name": "13 x64"}}
    decorated = wizard_service._overlay_droplet_windows_image(source, "win2022")

    assert source["image"]["distribution"] == "Debian"
    assert decorated["image"]["distribution"] == "Windows"
    assert decorated["image"]["name"] == "Windows Server 2022 DC"


def test_decorate_droplets_with_windows_labels_applies_by_droplet_id():
    droplets = [
        {"id": 1001, "image": {"distribution": "Debian", "name": "13 x64"}},
        {"id": 1002, "image": {"distribution": "Ubuntu", "name": "22.04 x64"}},
    ]

    decorated = wizard_service._decorate_droplets_with_windows_labels(
        droplets,
        {1002: "win11pro"},
    )

    assert decorated[0]["image"]["distribution"] == "Debian"
    assert decorated[1]["image"]["distribution"] == "Windows"
    assert decorated[1]["image"]["name"] == "Windows 11 Pro"
