.PHONY: run install-user uninstall-user

run:
	PYTHONPATH=src python -m omnote

install-user:
	install -Dm644 dist/dev.omarchy.MicroPad.desktop ~/.local/share/applications/dev.omarchy.MicroPad.desktop
	install -Dm644 assets/dev.omarchy.MicroPad.svg ~/.local/share/icons/hicolor/256x256/apps/dev.omarchy.MicroPad.svg
	update-desktop-database ~/.local/share/applications || true
	update-icon-caches ~/.local/share/icons/hicolor || true

uninstall-user:
	rm -f ~/.local/share/applications/dev.omarchy.MicroPad.desktop
	rm -f ~/.local/share/icons/hicolor/256x256/apps/dev.omarchy.MicroPad.svg
	update-desktop-database ~/.local/share/applications || true
	update-icon-caches ~/.local/share/icons/hicolor || true
