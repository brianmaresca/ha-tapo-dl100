# Tapo DL100 Home Assistant Integration

Custom Home Assistant integration for TP-Link Tapo DL100 locks.

## Features

- Adds DL100 as a Home Assistant `lock` entity
- Supports lock and unlock actions
- Polls lock status and battery information
- Config flow setup from Home Assistant UI

## Installation (HACS Custom Repository)

1. Push this repository to GitHub.
2. Create a release tag (for example `v0.1.0`).
3. In Home Assistant, open HACS.
4. Go to **HACS -> Menu -> Custom repositories**.
5. Add your repository URL and choose **Integration** as category.
6. Install **Tapo DL100** from HACS.
7. Restart Home Assistant.

## Manual Installation

1. Copy `custom_components/tapo_dl100` to your Home Assistant config directory under `custom_components`.
2. Restart Home Assistant.
3. Go to **Settings -> Devices & Services -> Add Integration**.
4. Search for **Tapo DL100**.
5. Enter:
   - lock name
   - lock local IP
   - TP-Link cloud username
   - TP-Link cloud password

## Notes

- If your TP-Link account has multiple DL100 locks, the integration `name` must match the lock alias in the Tapo app exactly.
- `lock_status` mapping:
  - `0` = locked
  - `1` = unlocked

## Credits

- This integration is based on reverse-engineering and protocol work from Ted Holtz's Homebridge project: [tedholtz/homebridge-tapo-dl100](https://github.com/tedholtz/homebridge-tapo-dl100).