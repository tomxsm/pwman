"""CustomTkinter interface: unlock screen + main vault screen."""
import sys
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk
from cryptography.fernet import InvalidToken

import clipboard
import config
import crypto
import db
import generator


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("PwMan")
        self.geometry("460x640")
        self.minsize(420, 540)
        self.set_window_icon()

        self.fernet = None
        self._clear_job = None
        self._last_copied = None

        db.init_db()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.show_login()

    # ------------------------------------------------------------------ utils
    def set_window_icon(self):
        if sys.platform != "win32" or not config.ICON_PATH.exists():
            return

        def apply():
            try:
                self.iconbitmap(str(config.ICON_PATH))
            except tk.TclError:
                pass

        # CustomTkinter sets its own default icon ~200 ms after startup,
        # so we set ours slightly later to override it.
        self.after(250, apply)

    def _reset(self):
        for w in self.winfo_children():
            w.destroy()

    def copy_to_clipboard(self, text: str):
        # Preferred: Windows API call that keeps it out of Win+V history / cloud sync.
        # Fallback: normal Tkinter clipboard.
        if not clipboard.copy_secret(text, self.winfo_id()):
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        self._last_copied = text
        if self._clear_job:
            self.after_cancel(self._clear_job)
        self._clear_job = self.after(config.CLIPBOARD_CLEAR_MS, self._clear_clipboard)

    def _clear_clipboard(self):
        """Clear the clipboard, but only if it still holds what we put there."""
        self._clear_job = None
        if self._last_copied is not None:
            if not clipboard.clear_if_equal(self._last_copied, self.winfo_id()):
                try:
                    current = self.clipboard_get()
                except tk.TclError:
                    current = None
                if current == self._last_copied:
                    self.clipboard_clear()
                    self.update()
        self._last_copied = None

    def on_close(self):
        self._clear_clipboard()
        self.destroy()

    # ----------------------------------------------------------------- login
    def show_login(self):
        self._reset()
        self.fernet = None
        self.first_run = db.get_meta("check") is None

        frame = ctk.CTkFrame(self)
        frame.pack(expand=True, padx=30, pady=30, fill="x")

        title = "Create master password" if self.first_run else "Unlock vault"
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(24, 8))

        if self.first_run:
            hint = (f"At least {config.MIN_MASTER_LENGTH} characters.\n"
                    "There is NO recovery if you forget it.")
            ctk.CTkLabel(frame, text=hint, text_color="gray70").pack(pady=(0, 12))

        self.pw_entry = ctk.CTkEntry(frame, placeholder_text="Master password", show="•", width=280)
        self.pw_entry.pack(pady=6)
        self.pw_entry.bind("<Return>", lambda e: self.submit_login())

        if self.first_run:
            self.confirm_entry = ctk.CTkEntry(frame, placeholder_text="Confirm master password",
                                              show="•", width=280)
            self.confirm_entry.pack(pady=6)
            self.confirm_entry.bind("<Return>", lambda e: self.submit_login())

        btn_text = "Create vault" if self.first_run else "Unlock"
        ctk.CTkButton(frame, text=btn_text, width=280, command=self.submit_login).pack(pady=(14, 24))
        self.pw_entry.focus()

    def submit_login(self):
        pw = self.pw_entry.get()

        if self.first_run:
            if len(pw) < config.MIN_MASTER_LENGTH:
                messagebox.showerror("Too short",
                                     f"Use at least {config.MIN_MASTER_LENGTH} characters.")
                return
            if pw != self.confirm_entry.get():
                messagebox.showerror("Mismatch", "The two passwords don't match.")
                return
            salt = crypto.create_salt()
            f = crypto.make_fernet(pw, salt)
            db.set_meta("check", crypto.make_check(f))
        else:
            if not config.SALT_PATH.exists():
                messagebox.showerror("Missing file",
                                     f"{config.SALT_PATH} is missing. Without it the vault "
                                     "can't be unlocked. Restore it from a backup.")
                return
            f = crypto.make_fernet(pw, crypto.load_salt())
            if not crypto.verify_check(f, db.get_meta("check")):
                messagebox.showerror("Wrong password", "That master password is incorrect.")
                self.pw_entry.delete(0, "end")
                return

        self.fernet = f
        self.show_main()

    # ------------------------------------------------------------------ main
    def show_main(self):
        self._reset()

        # --- Add / generate section
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=14, pady=(14, 8))

        self.label_entry = ctk.CTkEntry(top, placeholder_text="What is it for? (e.g. Steam account 2)")
        self.label_entry.pack(fill="x", padx=12, pady=(12, 6))

        self.custom_entry = ctk.CTkEntry(top, placeholder_text="Existing password (leave blank to generate)",
                                         show="•")
        self.custom_entry.pack(fill="x", padx=12, pady=6)

        opts = ctk.CTkFrame(top, fg_color="transparent")
        opts.pack(fill="x", padx=12, pady=4)
        self.length_var = tk.IntVar(value=20)
        self.length_lbl = ctk.CTkLabel(opts, text="Length: 20", width=80, anchor="w")
        self.length_lbl.pack(side="left")
        ctk.CTkSlider(opts, from_=8, to=64, number_of_steps=56, variable=self.length_var,
                      command=lambda v: self.length_lbl.configure(text=f"Length: {int(v)}")
                      ).pack(side="left", fill="x", expand=True, padx=8)
        self.symbols_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opts, text="Symbols", variable=self.symbols_var, width=70).pack(side="left")

        ctk.CTkButton(top, text="Generate & Save", command=self.on_save).pack(
            fill="x", padx=12, pady=(8, 12))
        self.label_entry.bind("<Return>", lambda e: self.on_save())

        # --- Saved entries
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        ctk.CTkEntry(header, placeholder_text="Search…", textvariable=self.search_var).pack(
            side="left", fill="x", expand=True)
        ctk.CTkButton(header, text="Lock", width=60, fg_color="gray30", hover_color="gray40",
                      command=self.lock).pack(side="left", padx=(8, 0))

        self.list_frame = ctk.CTkScrollableFrame(self, label_text="Click an entry to copy its password")
        self.list_frame.pack(fill="both", expand=True, padx=14, pady=8)

        self.status = ctk.CTkLabel(self, text="", text_color="gray70")
        self.status.pack(pady=(0, 10))

        self.refresh_list()

    def refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        query = self.search_var.get().strip().lower()
        for label in db.list_labels():
            if query and query not in label.lower():
                continue
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkButton(row, text=label, anchor="w",
                          command=lambda l=label: self.copy_entry(l)
                          ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="✕", width=32, fg_color="gray30", hover_color="#a33",
                          command=lambda l=label: self.delete(l)).pack(side="left", padx=(6, 0))

    def set_status(self, text: str):
        self.status.configure(text=text)

    def on_save(self):
        label = self.label_entry.get().strip()
        if not label:
            messagebox.showerror("Missing label", "Type what this password is for first.")
            return
        if db.label_exists(label):
            if not messagebox.askyesno("Already exists",
                                       f"'{label}' already exists. Overwrite its password?"):
                return

        password = self.custom_entry.get() or generator.generate_password(
            self.length_var.get(), self.symbols_var.get())

        db.save_entry(label, crypto.encrypt(self.fernet, password))
        self.copy_to_clipboard(password)

        self.label_entry.delete(0, "end")
        self.custom_entry.delete(0, "end")
        self.refresh_list()
        self.set_status(f"Saved '{label}' and copied. Clipboard clears in "
                        f"{config.CLIPBOARD_CLEAR_MS // 1000}s.")

    def copy_entry(self, label: str):
        token = db.get_encrypted(label)
        if token is None:
            return
        try:
            password = crypto.decrypt(self.fernet, token)
        except InvalidToken:
            messagebox.showerror("Decrypt failed", "Couldn't decrypt this entry.")
            return
        self.copy_to_clipboard(password)
        self.set_status(f"Copied '{label}'. Clipboard clears in "
                        f"{config.CLIPBOARD_CLEAR_MS // 1000}s.")

    def delete(self, label: str):
        if messagebox.askyesno("Delete", f"Delete '{label}'? This can't be undone."):
            db.delete_entry(label)
            self.refresh_list()
            self.set_status(f"Deleted '{label}'.")

    def lock(self):
        self._clear_clipboard()
        self.show_login()