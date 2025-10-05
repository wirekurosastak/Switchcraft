import os
import subprocess
import webbrowser
import yaml
import requests
import customtkinter as ctk
from tkinter import messagebox
from vcolorpicker import getColor, useLightTheme
from collections import defaultdict

# --- Constants ---
WINSANE_FOLDER = r"C:\Winsane"
TWEAKS_FILE = os.path.join(WINSANE_FOLDER, "data.yaml")
GITHUB_RAW_URL = "https://raw.githubusercontent.com/wirekurosastak/Switchcraft/main/data.yaml"
ACCENT_COLOR = "#3B8ED0"

# --- Helpers ---
def darker(hex_color, factor=0.8):
    c = hex_color.lstrip("#")
    r, g, b = [int(c[i:i+2],16) for i in (0,2,4)]
    return "#%02x%02x%02x" % (int(r*factor), int(g*factor), int(b*factor))

def run_powershell_as_admin(command):
    if not command.strip(): return
    try:
        subprocess.run([
            "powershell","-Command",
            f"Start-Process powershell -ArgumentList \"{command}\" -Verb RunAs -WindowStyle Hidden"
        ], check=True)
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Command failed:\n{e}")

# --- Config ---
def ensure_winsane_folder():
    os.makedirs(WINSANE_FOLDER, exist_ok=True)
    legacy_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.yaml")
    if os.path.exists(legacy_file):
        try: os.remove(legacy_file)
        except: pass

def save_tweaks(data):
    try:
        with open(TWEAKS_FILE,"w",encoding="utf-8") as f:
            yaml.safe_dump(data,f,allow_unicode=True,indent=2,sort_keys=False)
    except Exception as e:
        messagebox.showerror("Save Error", f"Error saving configuration:\n{e}")

def load_local_config(path):
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            messagebox.showerror("File Error", f"Local load failed:\n{e}")
    return None

def fetch_remote_config(url,timeout=5):
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return yaml.safe_load(resp.text)
    except Exception:
        messagebox.showinfo("Network Error", "Failed to fetch config from GitHub.\nLocal configuration will be used if available.")
        return None

def merge_configs(remote, local):
    if not remote: return local
    theme_backup = local.get("theme",{}).copy() if local else {}
    enabled_map = {(feat["feature"], cat["category"], item["name"]): item.get("enabled", False)
                   for feat in (local or {}).get("tweaks", [])
                   for cat in feat.get("categories", [])
                   for item in cat.get("items", [])}
    for feat in remote.get("tweaks", []):
        for cat in feat.get("categories", []):
            for item in cat.get("items", []):
                key = (feat["feature"], cat["category"], item["name"])
                item["enabled"] = enabled_map.get(key, item.get("enabled", False))
    if theme_backup:
        remote["theme"] = theme_backup
    return remote

# --- Initialize Config ---
ensure_winsane_folder()
local_data = load_local_config(TWEAKS_FILE)
remote_data = fetch_remote_config(GITHUB_RAW_URL)
if local_data:
    global_tweak_data = merge_configs(remote_data, local_data) if remote_data else local_data
else:
    global_tweak_data = remote_data
if global_tweak_data: save_tweaks(global_tweak_data)

# --- GUI Components ---
class TweakItemControl(ctk.CTkFrame):
    def __init__(self, master, item, all_data, **kwargs):
        super().__init__(master, **kwargs)
        self.item = item
        self.all_data = all_data
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=item['name'], font=ctk.CTkFont(weight="bold", size=14),
                     text_color=("black","white")).grid(row=0,column=0,padx=15,pady=(5,0),sticky="w")
        ctk.CTkLabel(self, text=item.get('purpose','No description.'), wraplength=450,
                     justify="left", fg_color="transparent", text_color=("gray30","gray70")
        ).grid(row=1,column=0,padx=15,pady=(0,5),sticky="w")

        self.tweak_var = ctk.BooleanVar(value=item.get('enabled',False))
        self.tweak_switch = ctk.CTkSwitch(self, text="", variable=self.tweak_var,
                                          command=self.toggle_tweak, progress_color=ACCENT_COLOR)
        self.tweak_switch.grid(row=0,column=1,rowspan=2,padx=20,pady=10,sticky="e")

    def toggle_tweak(self):
        is_on = self.tweak_var.get()
        command = self.item.get(is_on,'')
        run_powershell_as_admin(command)
        self.item['enabled'] = is_on
        save_tweaks(self.all_data)

class SubTabView(ctk.CTkTabview):
    def __init__(self, master, categories_data, root_data, feature_name, **kwargs):
        super().__init__(master, **kwargs)
        hover_col = darker(ACCENT_COLOR,0.85)
        self.configure(
            text_color=("black","white"),
            segmented_button_selected_color=(ACCENT_COLOR,ACCENT_COLOR),
            segmented_button_selected_hover_color=(hover_col,hover_col),
            segmented_button_unselected_color=("#E5E5E5","#2B2B2B"),
            segmented_button_unselected_hover_color=("#D5D5D5","#3B3B3B")
        )
        category_map = defaultdict(list)
        for cat_entry in categories_data:
            category_map[cat_entry['category']].extend(cat_entry.get('items',[]))
        for category_name, items in category_map.items():
            self.add(category_name)
            # Fixed label width
            label = ctk.CTkLabel(self.tab(category_name), 
                                text="Please restart your computer after desired tweaks are set.",
                                text_color=("black","white"))
            label.pack(pady=(10,0))
            
            scroll_frame = ctk.CTkScrollableFrame(self.tab(category_name))
            scroll_frame.pack(fill="both",expand=True,padx=10,pady=10)
            for item in items:
                TweakItemControl(scroll_frame,item=item,all_data=root_data,
                                 fg_color=("white","gray15")).pack(fill="x",pady=5,padx=5)

class MainTabView(ctk.CTkTabview):
    def __init__(self, master, all_data, **kwargs):
        super().__init__(master, **kwargs)
        hover_col = darker(ACCENT_COLOR,0.85)
        self.configure(
            text_color=("black","white"),
            segmented_button_selected_color=(ACCENT_COLOR,ACCENT_COLOR),
            segmented_button_selected_hover_color=(hover_col,hover_col),
            segmented_button_unselected_color=("#E5E5E5","#2B2B2B"),
            segmented_button_unselected_hover_color=("#D5D5D5","#3B3B3B")
        )
        for main_tab in all_data.get('tweaks',[]):
            tab_name = main_tab.get('feature')
            if not tab_name: continue
            self.add(tab_name)
            categories = main_tab.get('categories',[])
            if categories:
                SubTabView(self.tab(tab_name),categories,all_data,tab_name).pack(fill="both",expand=True,padx=5,pady=5)
            else:
                ctk.CTkLabel(self.tab(tab_name),text=f"'{tab_name}' content coming soon...",
                             text_color=("black","white")).pack(pady=20,padx=20)

class PowerTimer(ctk.CTkToplevel):
    def __init__(self,parent):
        super().__init__(parent)
        self.title("Power Scheduler")
        self.geometry("335x150")
        self.grab_set()
        self.resizable(False,False)
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self.input_hour = self._create_entry("Hours",10)
        self.input_min = self._create_entry("Minutes",40)
        self.input_sec = self._create_entry("Seconds",70)

        hover_col = darker(ACCENT_COLOR,0.85)
        for text, cmd, x in [("Shutdown",self.shutdown,10),
                              ("Restart",self.restart,90),
                              ("BIOS",self.bios,170),
                              ("Cancel",self.destroy,250)]:
            ctk.CTkButton(self,text=text,command=cmd,width=75,
                          fg_color=ACCENT_COLOR, hover_color=hover_col).place(x=x,y=110)

    def _create_entry(self,label,y):
        ctk.CTkLabel(self,text=label).place(x=10,y=y)
        entry = ctk.CTkEntry(self,width=255)
        entry.insert(0,"0")
        entry.place(x=70,y=y)
        return entry

    def get_total_seconds(self):
        try:
            return int(self.input_hour.get())*3600 + int(self.input_min.get())*60 + int(self.input_sec.get())
        except ValueError:
            messagebox.showerror("Error","Please enter valid numbers.")
            return None

    def shutdown(self): self._do("'-s','-f'")
    def restart(self): self._do("'-r','-f'")
    def bios(self): self._do("'-r','-fw'")

    def _do(self,args):
        total = self.get_total_seconds()
        if total is not None:
            run_powershell_as_admin(f"Start-Process shutdown -ArgumentList {args},'-t {total}'")
            self.destroy()

# --- Tooltip class ---
class Tooltip(ctk.CTkToplevel):
    def __init__(self,parent,text):
        super().__init__(parent)
        self.wm_overrideredirect(True)
        self.attributes("-topmost",True)
        self.configure(fg_color=("white","#333333"), corner_radius=12)
        self.label = ctk.CTkLabel(self,text=text,text_color=("black","white"),
                                   fg_color=("white","#333333"))
        self.label.pack(padx=8,pady=4)
        self.withdraw()
    def show(self,x,y):
        self.geometry(f"+{x}+{y}")
        self.deiconify()
    def hide(self):
        self.withdraw()

def add_tooltip(widget,text):
    tip = Tooltip(widget,text)
    def on_enter(event):
        x = widget.winfo_rootx() + widget.winfo_width() + 5
        y = widget.winfo_rooty()
        tip.show(x,y)
    def on_leave(event):
        tip.hide()
    widget.bind("<Enter>",on_enter)
    widget.bind("<Leave>",on_leave)

# --- Main App ---
class Winsane(ctk.CTk):
    def __init__(self, tweak_data):
        super().__init__()
        global ACCENT_COLOR
        if not tweak_data or 'tweaks' not in tweak_data:
            self.destroy(); return

        theme_data = tweak_data.get("theme", {})
        if isinstance(theme_data, dict):
            self.current_theme = theme_data.get("mode", "system")
            ACCENT_COLOR = theme_data.get("accent_color", ACCENT_COLOR)
        else:
            self.current_theme = theme_data if theme_data in ["dark", "light", "system"] else "system"

        ctk.set_appearance_mode(self.current_theme)
        useLightTheme(ctk.get_appearance_mode() == "Light")

        self.root_data = tweak_data
        self.title("Winsane")
        
        # Smooth startup
        self.attributes('-alpha', 0.0)
        self.update()
        self.state("zoomed")
        
        self.grid_columnconfigure(0, weight=0, minsize=60)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=60, fg_color=("#EBEBEB","#242424"))
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(0, weight=1)
        sidebar.grid_rowconfigure(5, weight=1)

        btn_cfg = dict(width=40, height=40, font=ctk.CTkFont(size=14),
                       text_color=("black","white"), corner_radius=8,
                       fg_color=("#d0d0d0","#333333"), hover_color=("#c0c0c0","#444444"))

        b_theme = ctk.CTkButton(sidebar, text="☼", command=self.toggle_theme, **btn_cfg)
        b_color = ctk.CTkButton(sidebar, text="🎨", command=self.pick_color, **btn_cfg)
        b_power = ctk.CTkButton(sidebar, text="⏻", command=lambda: PowerTimer(self), **btn_cfg)
        b_github = ctk.CTkButton(sidebar, text="🐱", command=self.open_github, **btn_cfg)

        buttons = [b_theme, b_color, b_power, b_github]
        for i, btn in enumerate(buttons, start=1):
            btn.grid(row=i, column=0, pady=5, padx=10)

        add_tooltip(b_theme, "Theme")
        add_tooltip(b_color, "Accent Color")
        add_tooltip(b_power, "Power Scheduler")
        add_tooltip(b_github, "GitHub")

        MainTabView(self, tweak_data).grid(row=0, column=1, padx=(3, 60), pady=(10, 30), sticky="nsew")
        
        # Fade in
        self.fade_in()

    def fade_in(self):
        for i in range(0, 11):
            self.attributes('-alpha', i/10)
            self.update()
            self.after(20)

    def toggle_theme(self):
        # Fade out completely to transparent
        for i in range(0, 11):
            self.attributes('-alpha', 1.0 - (i/10))
            self.update()
            self.after(40)  # Longer delay for smoother transition
        
        # Change theme when fully transparent
        self.current_theme = {"system":"dark","dark":"light","light":"system"}[self.current_theme]
        ctk.set_appearance_mode(self.current_theme)
        useLightTheme(ctk.get_appearance_mode() == "Light")
        
        # Ensure color picker theme is updated
        useLightTheme(self.current_theme == "light")
        
        # Fade back in from transparent
        for i in range(0, 11):
            self.attributes('-alpha', i/10)
            self.update()
            self.after(40)  # Longer delay for smoother transition
        
        if "theme" not in self.root_data:
            self.root_data["theme"] = {}
        self.root_data["theme"]["mode"] = self.current_theme
        save_tweaks(self.root_data)

    def pick_color(self):
        global ACCENT_COLOR
        color = getColor()
        if not color or color == (0,0,0):
            return
        # Ensure we got an RGB tuple of length 3
        if isinstance(color, tuple) and len(color) == 3:
            ACCENT_COLOR = "#%02x%02x%02x" % tuple(map(int, color))
            if "theme" not in self.root_data or not isinstance(self.root_data.get("theme"), dict):
                self.root_data["theme"] = {}
            self.root_data["theme"]["accent_color"] = ACCENT_COLOR
            save_tweaks(self.root_data)
            self.refresh_accent()

    def refresh_accent(self):
        hover_col = darker(ACCENT_COLOR, 0.85)
        def update(widget):
            if isinstance(widget, ctk.CTkSwitch):
                widget.configure(progress_color=ACCENT_COLOR)
            elif isinstance(widget, ctk.CTkTabview):
                widget.configure(segmented_button_selected_color=(ACCENT_COLOR, ACCENT_COLOR),
                                 segmented_button_selected_hover_color=(hover_col, hover_col))
            elif isinstance(widget, ctk.CTkButton) and widget.cget("text") in ["Shutdown","Restart","BIOS"]:
                widget.configure(fg_color=ACCENT_COLOR, hover_color=hover_col)
            for w in widget.winfo_children():
                update(w)
        update(self)

    def open_github(self): 
        webbrowser.open_new_tab("https://github.com/wirekurosastak/Winsane")

# --- Start App ---
if global_tweak_data:
    app = Winsane(global_tweak_data)
    app.mainloop()
