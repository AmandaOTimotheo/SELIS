import json
import queue
import subprocess
import sys
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pydantic import ValidationError

from parameters_model_v2 import ParametersV2


TOP_LEVEL_ORDER = [
    "debug",
    "path_json",
    "collision",
    "clustering",
    "simulation",
    "financial",
]

HELP_TEXT = {
    "debug": "Enable debug mode. If true, publisher waits for a debugger on port 5678.",
    "path_json": "Directory where used_parameters_YYYYMMDD_HHMMSS.json will be saved.",
    "collision.enable": "Enable message collision analysis reports.",
    "collision.save_data_path": "Directory to store collision_report.csv.",
    "clustering.clustering": "Enable clustering process for device generation.",
    "clustering.generate_density_map": "Enable generation of the raw density map (HTML).",
    "clustering.generate_clustered_map": "Enable generation of clustered map (HTML).",
    "clustering.raw_database.path": "Input CSV path for raw streetlight database.",
    "clustering.final_path": "Directory where clustered outputs will be saved.",
    "simulation.window.use_current_time_and_date": "Use current date/time instead of manual window.",
    "simulation.window.simulation_start_date": "Format: MM/DD/YYYY",
    "simulation.window.simulation_stop_date": "Format: MM/DD/YYYY",
    "simulation.window.simulation_start_time": "Format: HH:MM",
    "simulation.window.simulation_stop_time": "Format: HH:MM",
    "simulation.devices.panel.modes.offline_simulation.enable": (
        "Offline and real-time modes are mutually exclusive per device."
    ),
    "simulation.devices.panel.modes.real_time_simulation.enable": (
        "Offline and real-time modes are mutually exclusive per device."
    ),
    "simulation.devices.edge_fog.modes.offline_simulation.enable": (
        "Offline and real-time modes are mutually exclusive per device."
    ),
    "simulation.devices.edge_fog.modes.real_time_simulation.enable": (
        "Offline and real-time modes are mutually exclusive per device."
    ),
}

DIRECTORY_PATH_FIELDS = {
    "path_json",
    "collision.save_data_path",
    "clustering.final_path",
    "financial.general.save_report_path",
    "simulation.devices.panel.modes.offline_simulation.save_data_path",
    "simulation.devices.edge_fog.modes.offline_simulation.save_data_path",
}

FILE_PATH_FIELDS = {
    "clustering.raw_database.path",
    "simulation.devices.panel.database.path",
    "simulation.devices.edge_fog.database.path",
}

HIDE_WHEN_CLUSTERING_DISABLED = {
    "clustering.raw_database",
    "clustering.final_path",
    "clustering.devices",
}

HIDE_WHEN_COLLISION_DISABLED = {
    "collision.save_data_path",
    "collision.num_edges",
    "collision.msg_transmission_time",
    "collision.t_simulation_cycles",
    "collision.transmission_interval_edge",
    "collision.num_channels",
    "collision.poisson_calculation_enable",
    "collision.monte_carlo_simulation_enable",
}


def deep_get(data: dict, path: list[str], default: Any = None) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def deep_set(data: dict, path: list[str], value: Any) -> None:
    current = data
    for key in path[:-1]:
        current = current.setdefault(key, {})
    current[path[-1]] = value


def build_type_map(data: Any, prefix: tuple[str, ...] = ()) -> dict[str, type]:
    type_map: dict[str, type] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            type_map.update(build_type_map(value, prefix + (str(key),)))
    else:
        type_map[".".join(prefix)] = type(data)
    return type_map


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        self.widget.bind("<Enter>", self._show)
        self.widget.bind("<Leave>", self._hide)

    def _show(self, _event):
        if self.tip_window is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=4,
            bg="#ffffe0",
        )
        label.pack()

    def _hide(self, _event):
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class CollapsibleFrame(ttk.Frame):
    def __init__(self, parent, title: str, expanded: bool = True):
        super().__init__(parent)
        self._expanded = expanded

        header = ttk.Frame(self)
        header.pack(fill="x")

        self.toggle_btn = ttk.Button(header, width=2, command=self.toggle)
        self.toggle_btn.pack(side="left")
        ttk.Label(header, text=title, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(6, 0))

        self.content = ttk.Frame(self)
        self._refresh()

    def _refresh(self):
        self.toggle_btn.configure(text="-" if self._expanded else "+")
        if self._expanded:
            self.content.pack(fill="x", padx=8, pady=(4, 0))
        else:
            self.content.pack_forget()

    def toggle(self):
        self._expanded = not self._expanded
        self._refresh()


class ParametersGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Generator Math - Parameters GUI")
        self.geometry("1400x900")

        self.script_dir = Path(__file__).resolve().parent
        self.publisher_dir = self.script_dir.parent
        self.default_json_path = self._resolve_default_json_path()
        self.template_json_path = self._resolve_template_json_path()
        self.publisher_script = self.script_dir / "publisher.py"

        self.params_data: dict[str, Any] = {}
        self.base_type_map: dict[str, type] = {}
        self.type_map: dict[str, type] = {}
        self.field_vars: dict[str, dict[str, Any]] = {}
        self.current_json_label = tk.StringVar(value="Source: (loading...)")
        self.status_text = tk.StringVar(value="Ready.")
        self._internal_update = False

        self.process: subprocess.Popen | None = None
        self.worker: threading.Thread | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()

        self._load_default_data()
        self._build_layout()
        self._render_form()

    def _resolve_default_json_path(self) -> Path | None:
        candidates = [
            self.publisher_dir / "source" / "default.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _resolve_template_json_path(self) -> Path | None:
        candidate = self.publisher_dir / "source" / "parameters2.json"
        return candidate if candidate.exists() else None

    def _blank_template(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._blank_template(child) for key, child in value.items()}
        if isinstance(value, list):
            return []
        if isinstance(value, bool):
            return False
        return None

    def _load_default_data(self):
        if self.default_json_path and self.default_json_path.exists():
            with self.default_json_path.open("r", encoding="utf-8") as file:
                self.params_data = json.load(file)
            self.base_type_map = build_type_map(self.params_data)
            self.type_map = dict(self.base_type_map)
            self.current_json_label.set(f"Source: {self.default_json_path}")
            return

        if self.template_json_path and self.template_json_path.exists():
            with self.template_json_path.open("r", encoding="utf-8") as file:
                template = json.load(file)
            self.base_type_map = build_type_map(template)
            self.type_map = dict(self.base_type_map)
            self.params_data = self._blank_template(template)
            self.current_json_label.set(f"Source: {self.template_json_path} (blank)")
            return

        self.params_data = {}
        self.base_type_map = {}
        self.type_map = {}
        self.current_json_label.set("Source: (empty)")

    def _build_layout(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        ttk.Button(top, text="Import JSON", command=self.import_json).pack(side="left")
        ttk.Button(top, text="Reload Default", command=self.reload_default).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="Validate", command=self.validate_form).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="Save JSON As...", command=self.save_json_as).pack(side="left", padx=(6, 0))

        self.run_btn = ttk.Button(top, text="Run Program", command=self.run_program)
        self.run_btn.pack(side="left", padx=(20, 0))

        self.stop_btn = ttk.Button(top, text="Stop", command=self.stop_program, state="disabled")
        self.stop_btn.pack(side="left", padx=(6, 0))

        ttk.Label(top, textvariable=self.current_json_label).pack(side="left", padx=(20, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=6)

        bottom = ttk.Frame(self)
        bottom.pack(fill="both", padx=10, pady=(0, 10))

        ttk.Label(bottom, text="Execution output").pack(anchor="w")

        log_frame = ttk.Frame(bottom)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=10, wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        ttk.Label(self, textvariable=self.status_text).pack(anchor="w", padx=10, pady=(0, 8))

    def _render_form(self):
        self._sync_data_from_form(show_errors=False)
        self.field_vars.clear()

        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)

        keys = [k for k in TOP_LEVEL_ORDER if k in self.params_data]
        keys.extend(k for k in self.params_data.keys() if k not in keys)

        for key in keys:
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=key)
            scroll_container, inner = self._create_scrollable_tab(tab)
            scroll_container.pack(fill="both", expand=True)
            value = self.params_data[key]
            if isinstance(value, dict):
                self._render_dict(inner, value, (key,), depth=0)
            else:
                self._render_leaf(inner, key, value, (key,), depth=0)

    def _create_scrollable_tab(self, parent):
        container = ttk.Frame(parent)
        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)

        def _on_configure(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        inner.bind("<Configure>", _on_configure)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return container, inner

    def _render_dict(self, parent, data: dict[str, Any], path: tuple[str, ...], depth: int):
        for key, value in data.items():
            child_path = path + (str(key),)
            if not self._should_render(child_path):
                continue

            if isinstance(value, dict):
                expanded = depth <= 0
                section = CollapsibleFrame(parent, title=str(key), expanded=expanded)
                section.pack(fill="x", padx=8 + depth * 8, pady=4, anchor="n")
                self._render_dict(section.content, value, child_path, depth + 1)
            else:
                self._render_leaf(parent, str(key), value, child_path, depth)

    def _render_leaf(self, parent, key: str, value: Any, path: tuple[str, ...], depth: int):
        path_str = ".".join(path)
        expected_type = self.type_map.get(path_str, type(value))

        row = ttk.Frame(parent)
        row.pack(fill="x", padx=16 + depth * 8, pady=2)

        label = ttk.Label(row, text=key, width=38, anchor="w")
        label.pack(side="left")

        info = ttk.Label(row, text="[i]", foreground="#245c99")
        info.pack(side="left", padx=(2, 8))
        Tooltip(info, self._help_for(path_str))

        if expected_type is bool:
            var = tk.BooleanVar(value=bool(value))
            widget = ttk.Checkbutton(
                row,
                variable=var,
                command=lambda p=path_str: self._on_bool_changed(p),
            )
            widget.pack(side="left")
        else:
            var = tk.StringVar(value="" if value is None else str(value))
            widget = ttk.Entry(row, textvariable=var)
            widget.pack(side="left", fill="x", expand=True)

            if path_str in DIRECTORY_PATH_FIELDS or path_str in FILE_PATH_FIELDS:
                ttk.Button(
                    row,
                    text="...",
                    width=3,
                    command=lambda p=path_str: self._browse_path(p),
                ).pack(side="left", padx=(6, 0))

        self.field_vars[path_str] = {
            "var": var,
            "type": expected_type,
        }

    def _help_for(self, path_str: str) -> str:
        if path_str in HELP_TEXT:
            return HELP_TEXT[path_str]
        if path_str.endswith(".enable"):
            return "Enable/disable this block."
        if path_str.endswith(".path") or path_str.endswith("_path"):
            return "Filesystem path."
        if path_str.endswith("_date"):
            return "Date format: MM/DD/YYYY"
        if path_str.endswith("_time"):
            return "Time format: HH:MM"
        return f"Field: {path_str}"

    def _should_render(self, path: tuple[str, ...]) -> bool:
        path_str = ".".join(path)

        if any(path_str == item or path_str.startswith(item + ".") for item in HIDE_WHEN_COLLISION_DISABLED):
            if not self._bool_value("collision.enable"):
                return path_str == "collision.enable"

        if any(path_str == item or path_str.startswith(item + ".") for item in HIDE_WHEN_CLUSTERING_DISABLED):
            clustering_active = (
                self._bool_value("clustering.clustering")
                or self._bool_value("clustering.generate_density_map")
                or self._bool_value("clustering.generate_clustered_map")
            )
            if not clustering_active:
                return False

        if path_str.endswith(".offline_simulation.save_data_path"):
            mode_path = path_str.replace(".save_data_path", ".enable")
            return self._bool_value(mode_path)

        if ".real_time_simulation." in path_str and not path_str.endswith(".real_time_simulation.enable"):
            mode_prefix = path_str.split(".real_time_simulation.")[0]
            mode_path = f"{mode_prefix}.real_time_simulation.enable"
            return self._bool_value(mode_path)

        return True

    def _bool_value(self, path_str: str) -> bool:
        value = deep_get(self.params_data, path_str.split("."), default=False)
        return bool(value)

    def _browse_path(self, path_str: str):
        if path_str in DIRECTORY_PATH_FIELDS:
            selected = filedialog.askdirectory(title=f"Select directory for {path_str}")
        else:
            selected = filedialog.askopenfilename(title=f"Select file for {path_str}")
        if not selected:
            return
        if path_str in self.field_vars:
            self.field_vars[path_str]["var"].set(selected)

    def _on_bool_changed(self, path_str: str):
        if self._internal_update:
            return

        self._sync_data_from_form(show_errors=False)

        if self._violates_simulation_mode_rule(path_str):
            return

        self._sync_data_from_form(show_errors=False)
        self._render_form()

    def _violates_simulation_mode_rule(self, changed_path: str) -> bool:
        if not changed_path.endswith(".enable"):
            return False

        if ".offline_simulation.enable" in changed_path:
            other = changed_path.replace(".offline_simulation.enable", ".real_time_simulation.enable")
        elif ".real_time_simulation.enable" in changed_path:
            other = changed_path.replace(".real_time_simulation.enable", ".offline_simulation.enable")
        else:
            return False

        if changed_path not in self.field_vars or other not in self.field_vars:
            return False

        changed_value = bool(self.field_vars[changed_path]["var"].get())
        other_value = bool(self.field_vars[other]["var"].get())

        if changed_value and other_value:
            self._internal_update = True
            self.field_vars[changed_path]["var"].set(False)
            self._internal_update = False

            messagebox.showwarning(
                "Invalid selection",
                (
                    "offline_simulation.enable and real_time_simulation.enable "
                    "cannot both be true for the same device."
                ),
            )
            self._sync_data_from_form(show_errors=False)
            self._render_form()
            return True
        return False

    def _cast_value(self, raw: Any, expected_type: type) -> Any:
        if expected_type is bool:
            return bool(raw)

        text = str(raw).strip()

        if expected_type is int:
            if text == "":
                raise ValueError("integer value is empty")
            return int(text)

        if expected_type is float:
            if text == "":
                raise ValueError("float value is empty")
            return float(text.replace(",", "."))

        if expected_type is str:
            return text

        return raw

    def _collect_form_data(self, *, show_errors: bool) -> dict[str, Any] | None:
        data = deepcopy(self.params_data)
        for path_str, meta in self.field_vars.items():
            var = meta["var"]
            expected_type = meta["type"]

            raw_value = var.get()
            try:
                value = self._cast_value(raw_value, expected_type)
            except ValueError as exc:
                if show_errors:
                    messagebox.showerror("Invalid value", f"{path_str}: {exc}")
                return None

            deep_set(data, path_str.split("."), value)
        return data

    def _sync_data_from_form(self, *, show_errors: bool):
        data = self._collect_form_data(show_errors=show_errors)
        if data is not None:
            self.params_data = data

    def _format_validation_errors(self, exc: ValidationError) -> str:
        lines = []
        for err in exc.errors():
            loc = ".".join(str(item) for item in err.get("loc", []))
            msg = err.get("msg", "validation error")
            lines.append(f"- {loc}: {msg}")
        return "\n".join(lines)

    def validate_form(self, show_dialog: bool = True) -> tuple[ParametersV2, dict[str, Any]] | tuple[None, None]:
        collected = self._collect_form_data(show_errors=True)
        if collected is None:
            self.status_text.set("Validation failed.")
            return None, None

        try:
            model = ParametersV2(**collected)
        except ValidationError as exc:
            message = self._format_validation_errors(exc)
            self.status_text.set("Validation failed.")
            if show_dialog:
                messagebox.showerror("Validation error", message)
            return None, None

        self.params_data = collected
        self.type_map = dict(self.base_type_map)
        self.type_map.update(build_type_map(collected))
        self.status_text.set("Validation OK.")
        if show_dialog:
            messagebox.showinfo("Validation", "Parameters are valid.")
        self._render_form()
        return model, collected

    def import_json(self):
        file_path = filedialog.askopenfilename(
            title="Import parameters JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except Exception as exc:
            messagebox.showerror("Import error", f"Could not import JSON:\n{exc}")
            return

        if not isinstance(data, dict):
            messagebox.showerror("Import error", "JSON root must be an object.")
            return

        if "path_json" not in data:
            data["path_json"] = self.params_data.get("path_json", "/app/source/parameters")

        self.params_data = data
        self.type_map = dict(self.base_type_map)
        self.type_map.update(build_type_map(data))
        self.current_json_label.set(f"Source: {file_path}")
        self.status_text.set("JSON imported.")
        self._render_form()

    def reload_default(self):
        try:
            self._load_default_data()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        self.status_text.set("Default parameters reloaded.")
        self._render_form()

    def save_json_as(self):
        model, normalized = self.validate_form(show_dialog=False)
        if model is None:
            messagebox.showerror("Save error", "Fix validation errors before saving.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save parameters JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=4, ensure_ascii=False)

        self.status_text.set(f"Saved: {file_path}")
        messagebox.showinfo("Saved", f"JSON saved to:\n{file_path}")

    def _save_used_parameters(self, normalized: dict[str, Any], path_json: str) -> Path:
        output_dir = Path(path_json).expanduser()
        if not output_dir.is_absolute():
            output_dir = (self.publisher_dir / output_dir).resolve()

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"used_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=4, ensure_ascii=False)

        return output_path

    def run_program(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Running", "A process is already running.")
            return

        model, normalized = self.validate_form(show_dialog=False)
        if model is None:
            messagebox.showerror("Run error", "Fix validation errors before running.")
            return

        try:
            used_params_path = self._save_used_parameters(normalized, model.path_json)
        except Exception as exc:
            messagebox.showerror("Run error", f"Could not save used parameters:\n{exc}")
            return

        command = [
            sys.executable,
            str(self.publisher_script),
            "--params",
            str(used_params_path),
        ]

        self._append_log(f"$ {' '.join(command)}")
        self._append_log(f"Using parameters file: {used_params_path}")

        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_text.set("Program running...")

        self.worker = threading.Thread(
            target=self._run_command_worker,
            args=(command,),
            daemon=True,
        )
        self.worker.start()
        self.after(100, self._poll_log_queue)

    def _run_command_worker(self, command: list[str]):
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(self.script_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.log_queue.put(line.rstrip("\n"))
            code = self.process.wait()
            self.log_queue.put(f"[process finished with code {code}]")
        except Exception as exc:
            self.log_queue.put(f"[execution error] {exc}")
        finally:
            self.log_queue.put("__PROCESS_DONE__")

    def _poll_log_queue(self):
        finished = False
        while True:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break

            if line == "__PROCESS_DONE__":
                finished = True
            else:
                self._append_log(line)

        if finished:
            self.run_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.process = None
            self.status_text.set("Program finished.")
            return

        self.after(100, self._poll_log_queue)

    def stop_program(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._append_log("[termination requested]")
            self.status_text.set("Stopping process...")

    def _append_log(self, line: str):
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")


def main():
    app = ParametersGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
