# Setup & Running

## Prerequisites

- Flutter SDK 3.11+
- Desktop platform support enabled for your target OS:

```bash
flutter config --enable-windows-desktop   # Windows
flutter config --enable-macos-desktop     # macOS
flutter config --enable-linux-desktop     # Linux
```

---

## Install Dependencies

```bash
cd titan_trade_app
flutter pub get
```

---

## Run (Development)

```bash
flutter run -d windows   # or macos, linux
```

On first launch the app shows the setup screen, asking for the TitanTrade server URL
(e.g. `https://trade.praguefun.cz`). It validates by hitting `GET /api/health`, then
saves the URL to `SharedPreferences`. All subsequent launches skip the setup screen.

---

## Build (Release)

```bash
flutter build windows   # or macos, linux
```

Output is placed in `build/windows/runner/Release/` (or equivalent for your platform).

---

## Changing the Server URL

Go to **Settings** → enter the new URL → **Apply**. The app re-validates against
`/api/health` and reloads all providers immediately on success.
