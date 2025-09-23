import tkinter as tk
from tkinter import messagebox
import json
import sys
import subprocess
import ctypes
import logging
import jsonschema
import urllib.request

# --- ToggleSwitch Widget ---
class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, scale=1.0, on_color="turquoise", off_color="#555555", command=None, initial_state=False):
        width = int(60 * scale)
        height = int(28 * scale)
        super().__init__(parent, width=width, height=height, highlightthickness=0, bg=parent["bg"])
        self.width = width
        self.height = height
        self.on_color = on_color
        self.off_color = off_color
        self.command = command
        self.state = initial_state
        self.corner_radius = self.height // 2
        self.knob_radius = self.corner_radius - 4

        self.bg_rect = self.create_rounded_rect(2, 2, width-2, height-2, self.corner_radius, fill=self.off_color)
        knob_x = (self.width - self.corner_radius) if self.state else self.corner_radius
        self.knob = self.create_oval(knob_x - self.knob_radius, self.height//2 - self.knob_radius,
                                     knob_x + self.knob_radius, self.height//2 + self.knob_radius,
                                     fill="white", outline="")
        self.update_color()
        self.bind("<Button-1>", self.toggle)

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
                  x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
                  x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def toggle(self, event=None):
        self.state = not self.state
        self.animate_knob()
        self.update_color()
        if self.command:
            self.command(self.state)

    def update_color(self):
        self.itemconfig(self.bg_rect, fill=self.on_color if self.state else self.off_color)

    def animate_knob(self):
        target_x = (self.width - self.corner_radius) if self.state else self.corner_radius
        current_coords = self.coords(self.knob)
        current_x = (current_coords[0] + current_coords[2]) / 2
        step = 3 if target_x > current_x else -3

        def move():
            nonlocal current_x
            if abs(target_x - current_x) > 1:
                current_x += step
                self.move(self.knob, step, 0)
                self.after(5, move)
            else:
                dx = target_x - current_x
                self.move(self.knob, dx, 0)
        move()

    def get(self):
        return self.state

    def set(self, state: bool):
        self.state = state
        knob_x = (self.width - self.corner_radius) if state else self.corner_radius
        self.coords(self.knob, knob_x - self.knob_radius, self.height//2 - self.knob_radius,
                    knob_x + self.knob_radius, self.height//2 + self.knob_radius)
        self.update_color()


# --- Tooltip ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        widget.bind("<Enter>", self.show_tooltip)
        widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify="left",
                         background="#333333", foreground="white",
                         relief="solid", borderwidth=1, font=("Segoe UI", 9),
                         padx=5, pady=3)
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


# --- Main App ---
class OptimizerApp:
    def __init__(self, root):
        self.root = root
        self.setup_logging()
        self.switches = {}

        root.state('zoomed')
        root.configure(bg="#1a1f52")
        root.title("Windows 11 Optimizer")

        # Dynamic scaling
        self.scale_factor = root.winfo_screenwidth() / 1920
        self.font_large = ("Segoe UI Semibold", int(16 * self.scale_factor))
        self.font_medium = ("Segoe UI Semibold", int(12 * self.scale_factor))
        self.font_small = ("Segoe UI Semibold", int(10 * self.scale_factor))

        header = tk.Label(root, text="Windows 11 Optimizer", fg="white", bg="#1a1f52", font=self.font_large)
        header.pack(pady=15)

        main_frame = tk.Frame(root, bg="#1a1f52")
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.canvas = tk.Canvas(main_frame, bg="#1a1f52", highlightthickness=0, borderwidth=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.scrollable_frame = tk.Frame(self.canvas, bg="#1a1f52")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        # Mouse wheel scroll only
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.adjust_columns_width())

        # Load functions
        self.functions = self.load_functions()
        self.column_frames = []
        self.repopulate_columns_balanced()

    def adjust_columns_width(self):
        canvas_width = self.canvas.winfo_width()
        if canvas_width <= 0:
            return
        col_width = canvas_width // 4
        for col_frame in self.column_frames:
            col_frame.config(width=col_width)

    # --- REFINED: Height-balanced column layout ---
    def repopulate_columns_balanced(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.column_frames = []

        if not self.functions:
            return

        num_cols = 4
        columns_heights = [0] * num_cols
        for i in range(num_cols):
            col_frame = tk.Frame(self.scrollable_frame, bg="#1a1f52")
            col_frame.grid(row=0, column=i, sticky="nsew", padx=10)
            self.column_frames.append(col_frame)

        for category_data in self.functions:
            min_index = columns_heights.index(min(columns_heights))
            self.add_category_to_frame(category_data, self.column_frames[min_index])
            # Approximate height by number of items + 1 for header
            columns_heights[min_index] += len(category_data['items']) + 1

        self.adjust_columns_width()

    def add_category_to_frame(self, category_data, parent_frame):
        category_label = tk.Label(parent_frame, text=f"─── {category_data['category']} ───",
                                  fg="white", bg="#1a1f52", font=self.font_medium)
        category_label.pack(pady=(15,5), anchor="w")

        wrap_length = int(self.root.winfo_screenwidth()/4 - 60)

        for func in category_data['items']:
            frame = tk.Frame(parent_frame, bg="#1a1f52")
            frame.pack(anchor="w", pady=8, fill="x")

            label = tk.Label(frame, text=func['name'], fg="white", bg="#1a1f52",
                             font=self.font_small, wraplength=wrap_length, justify="left")
            label.pack(side="left", padx=10, fill="x", expand=True)
            ToolTip(label, func['purpose'])

            toggle = ToggleSwitch(frame, scale=self.scale_factor,
                                  on_color="turquoise", off_color="#555555",
                                  command=lambda state, name=func['name']: self.save_state(name, state),
                                  initial_state=func.get("enabled", False))
            toggle.pack(side="right", padx=10)
            self.switches[func["name"]] = toggle

    def setup_logging(self):
        logging.basicConfig(filename='windows_optimizer.log',
                            level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        logging.info("Application started")

    def load_functions(self):
        url = "https://raw.githubusercontent.com/wirekuro/wintooljson-fetch/main/functions.json"
        try:
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode("utf-8"))

            schema = {
                "type":"array",
                "items":{
                    "type":"object",
                    "properties":{
                        "category":{"type":"string"},
                        "items":{
                            "type":"array",
                            "items":{
                                "type":"object",
                                "properties":{
                                    "name":{"type":"string"},
                                    "purpose":{"type":"string"},
                                    "on":{"type":"string"},
                                    "off":{"type":"string"},
                                    "enabled":{"type":"boolean"}
                                },
                                "required":["name","purpose","on","off","enabled"]
                            }
                        }
                    },
                    "required":["category","items"]
                }
            }
            jsonschema.validate(instance=data, schema=schema)
            return data
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load JSON: {e}")
            logging.error(f"Error loading JSON: {e}")
            return []

    def execute_powershell_command(self, command, function_name):
        if not command.strip():
            return
        try:
            subprocess.run(["powershell.exe", "-ExecutionPolicy", "Restricted", "-NoProfile", "-Command", command],
                           check=True, capture_output=True, text=True, timeout=30)
            logging.info(f"Executed command for {function_name}")
        except Exception as e:
            messagebox.showerror("Execution Error", f"Error executing command for '{function_name}': {e}")
            logging.error(f"Execution error: {e}")

    def save_state(self, function_name, new_state):
        for category_data in self.functions:
            for func in category_data['items']:
                if func['name'] == function_name:
                    func['enabled'] = new_state
                    command_to_run = func.get('on' if new_state else 'off')
                    if command_to_run:
                        self.execute_powershell_command(command_to_run, function_name)
                    return

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if __name__ == "__main__":
    if not is_admin():
        messagebox.showerror("Admin Privileges Required",
                             "This application requires administrator privileges. Please right-click and 'Run as Administrator'.")
        sys.exit()

    root = tk.Tk()
    app = OptimizerApp(root)
    root.mainloop()