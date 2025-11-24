#-*- coding = utf-8 -*-
#@Time:2025/11/23 20:59
#@Author:Li Yu
#@File:todoapp_openai.py
#@Software:PyCharm

import customtkinter as ctk  # 引入现代UI库
from tkinter import ttk, messagebox
import tkinter as tk
import threading
import time
import base64
import io
import json
import os
from datetime import datetime
from PIL import Image, ImageGrab
from openai import OpenAI
from plyer import notification

# ================= 配置区域 =================
API_KEY = "填入你的APIkey"
BASE_URL = "填入你的AI服务商的地址"

# 设置外观模式: "System" (跟随系统), "Dark", "Light"
ctk.set_appearance_mode("System")
# 设置默认颜色主题: "blue" (默认), "green", "dark-blue"
ctk.set_default_color_theme("blue")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
DATA_FILE = "tasks.json"


# ================= AI 逻辑层 (保持不变) =================
class AIHandler:
    @staticmethod
    def encode_image(image):
        buffered = io.BytesIO()
        # 转换为RGB防止PNG透明通道在某些情况下的兼容问题
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    @staticmethod
    def analyze_content(content_type, data):
        # [修改1] 获取当前日期和星期几
        # 格式示例：2023-11-15 (Wednesday)
        # 加上星期几对判断 "下周三" 这种描述至关重要
        now = datetime.now()
        current_date_info = now.strftime("%Y-%m-%d (%A)")

        # [修改2] 在提示词中明确告诉 AI 今天是几号
        system_prompt = f"""  
        你是一个专业的任务管理助手。  
        【当前基准时间：{current_date_info}】  

        请分析用户的输入，提取待办事项。  
        如果用户使用相对时间描述（如"明天"、"下周二"、"三天后"），请基于【当前基准时间】计算出具体的日期格式 (YYYY-MM-DD HH:MM)。  
        如果用户只说了日期没说具体时间，默认设为 9:00。  

        严格返回 JSON 格式：  
        [{{"title": "标题", "deadline": "YYYY-MM-DD HH:MM", "description": "详情"}}]  
        若无任务返回 []。  
        """

        messages = [{"role": "system", "content": system_prompt}]

        try:
            if content_type == "text":
                messages.append({"role": "user", "content": f"分析这段文字：{data}"})
            elif content_type == "image":
                base64_image = AIHandler.encode_image(data)
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "分析这张截图中的待办事项。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                })

            response = client.chat.completions.create(
                model="填入你的模型名",
                messages=messages,
                temperature=0.1,  # 温度低一点，让计算更严谨
                response_format={"type": "json_object"}
            )
            result_text = response.choices[0].message.content
            data = json.loads(result_text)
            return data.get("tasks", list(data.values())[0]) if isinstance(data, dict) else data
        except Exception as e:
            print(f"AI Error: {e}")
            return []


            # ================= 数据管理层 (保持不变) =================


class TaskManager:
    def __init__(self):
        self.tasks = []
        self.load_tasks()

    def add_task(self, task):
        task['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.tasks.append(task)
        self.save_tasks()

    def remove_task(self, index):
        if 0 <= index < len(self.tasks):
            del self.tasks[index]
            self.save_tasks()

    def update_task(self, index, title, deadline, description):
        if 0 <= index < len(self.tasks):
            self.tasks[index]['title'] = title
            self.tasks[index]['deadline'] = deadline
            self.tasks[index]['description'] = description
            self.save_tasks()

    def save_tasks(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=4)

    def load_tasks(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
            except:
                self.tasks = []

            # ================= 现代 GUI 主程序 =================


class ModernTodoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. 窗口基础设置
        self.title("AI 智能待办 - Modern Edition")
        self.geometry("800x600")
        self.task_manager = TaskManager()
        self.last_image_hash = None

        # 布局网格配置
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # 让列表区域自动伸缩

        # --- 顶部输入区域 (Card 风格) ---
        self.top_frame = ctk.CTkFrame(self, corner_radius=10)
        self.top_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        self.entry_text = ctk.CTkEntry(self.top_frame, placeholder_text="输入文字，例如：明天下午3点开会...", height=40,
                                       font=("微软雅黑", 14))
        self.entry_text.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.entry_text.bind("<Return>", lambda e: self.on_text_analyze())

        self.btn_analyze = ctk.CTkButton(self.top_frame, text="AI 识别", command=self.on_text_analyze, height=40,
                                         font=("微软雅黑", 14, "bold"))
        self.btn_analyze.pack(side="right", padx=10, pady=10)

        # --- 中间列表区域 ---
        # 由于 CTk 没有原生 Treeview，我们需要用 Frame 包裹 ttk.Treeview 并美化它
        self.list_frame = ctk.CTkFrame(self, corner_radius=10)
        self.list_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        self.setup_treeview()

        # --- 底部操作栏 ---
        self.bottom_frame = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent")  # 透明背景
        self.bottom_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")

        self.status_label = ctk.CTkLabel(self.bottom_frame, text="系统就绪 | 正在监控剪贴板...", text_color="gray",
                                         anchor="w")
        self.status_label.pack(side="left", padx=10)

        self.btn_delete = ctk.CTkButton(self.bottom_frame, text="完成/删除", command=self.delete_selected,
                                        fg_color="#FF5252", hover_color="#D32F2F", width=100)
        self.btn_delete.pack(side="right", padx=(10, 0))

        self.btn_edit = ctk.CTkButton(self.bottom_frame, text="查看详情 / 编辑", command=self.open_detail_window,
                                      width=120)
        self.btn_edit.pack(side="right")

        # 初始化逻辑
        self.refresh_list()
        threading.Thread(target=self.monitor_clipboard, daemon=True).start()

    def setup_treeview(self):
        # 定义样式
        style = ttk.Style()
        style.theme_use("clam")  # 使用 clam 主题作为基础，因为它容易自定义

        # 配置 Treeview 颜色以适应深色/浅色模式
        bg_color = self.list_frame._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        text_color = self.list_frame._apply_appearance_mode(ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        field_bg = self.list_frame._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])

        style.configure("Treeview",
                        background="#2b2b2b",  # 这里为了演示效果固定深色，实际可做动态
                        foreground="white",
                        fieldbackground="#2b2b2b",
                        rowheight=35,
                        font=("微软雅黑", 11),
                        borderwidth=0)

        style.configure("Treeview.Heading",
                        background="#1f6aa5",
                        foreground="white",
                        font=("微软雅黑", 12, "bold"),
                        relief="flat")

        style.map("Treeview", background=[('selected', '#1f6aa5')])

        columns = ("title", "deadline", "desc")
        self.tree = ttk.Treeview(self.list_frame, columns=columns, show="headings", selectmode="browse",
                                 style="Treeview")

        self.tree.heading("title", text="任务标题")
        self.tree.heading("deadline", text="截止时间")
        self.tree.heading("desc", text="详情摘要")

        self.tree.column("title", width=200)
        self.tree.column("deadline", width=150, anchor="center")
        self.tree.column("desc", width=350)

        # 滚动条
        scrollbar = ctk.CTkScrollbar(self.list_frame, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side="right", fill="y", padx=10, pady=10)

        # 绑定双击
        self.tree.bind("<Double-1>", self.on_double_click)

        # ================= 逻辑功能区 =================

    def refresh_list(self):
        # 清空旧数据
        for item in self.tree.get_children():
            self.tree.delete(item)

        for task in self.task_manager.tasks:
            self.tree.insert("", "end", values=(
                task.get('title', ''),
                task.get('deadline', ''),
                task.get('description', '').replace('\n', ' ')  # 列表里只显示一行
            ))

    def on_double_click(self, event):
        if self.tree.selection():
            self.open_detail_window()

    def open_detail_window(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "请先选择一个任务")
            return

        index = self.tree.index(selected[0])
        task_data = self.task_manager.tasks[index]

        # 创建现代风格的子窗口
        top = ctk.CTkToplevel(self)
        top.title("任务详情")
        top.geometry("500x600")
        top.transient(self)  # 设为子窗口
        top.grab_set()  # 模态

        # 标题输入
        ctk.CTkLabel(top, text="任务标题", font=("微软雅黑", 14, "bold")).pack(anchor="w", padx=20, pady=(20, 5))
        entry_title = ctk.CTkEntry(top, font=("微软雅黑", 13))
        entry_title.pack(fill="x", padx=20)
        entry_title.insert(0, task_data.get('title', ''))

        # 时间输入
        ctk.CTkLabel(top, text="截止时间", font=("微软雅黑", 14, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        entry_deadline = ctk.CTkEntry(top, font=("微软雅黑", 13))
        entry_deadline.pack(fill="x", padx=20)
        entry_deadline.insert(0, task_data.get('deadline', ''))

        # 描述输入 (使用 Modern Textbox)
        ctk.CTkLabel(top, text="详细描述", font=("微软雅黑", 14, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        text_desc = ctk.CTkTextbox(top, font=("微软雅黑", 13), height=200)
        text_desc.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        text_desc.insert("0.0", task_data.get('description', ''))

        def save():
            new_title = entry_title.get()
            new_deadline = entry_deadline.get()
            new_desc = text_desc.get("0.0", "end").strip()

            self.task_manager.update_task(index, new_title, new_deadline, new_desc)
            self.refresh_list()
            top.destroy()
            self.show_temp_message("修改已保存")

        ctk.CTkButton(top, text="保存修改", command=save, height=40, font=("微软雅黑", 14, "bold")).pack(fill="x",
                                                                                                         padx=20,
                                                                                                         pady=20)

    def show_temp_message(self, msg, duration=3000):
        """在状态栏显示临时消息"""
        old_text = self.status_label.cget("text")
        self.status_label.configure(text=msg, text_color="#1f6aa5")  # 蓝色高亮
        self.after(duration, lambda: self.status_label.configure(text=old_text, text_color="gray"))

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected: return

        # 确认对话框 (使用原生 messagebox 因为 CTk 还没完善这个)
        if not messagebox.askyesno("确认", "确定要完成/删除这个任务吗？"):
            return

        index = self.tree.index(selected[0])
        self.task_manager.remove_task(index)
        self.refresh_list()
        self.show_temp_message("任务已完成")

        # ================= 异步处理区 =================

    def on_text_analyze(self):
        text = self.entry_text.get().strip()
        if not text: return

        self.entry_text.delete(0, "end")
        self.status_label.configure(text="AI正在思考...", text_color="#1f6aa5")
        threading.Thread(target=self._process_api, args=("text", text), daemon=True).start()

    def _process_api(self, c_type, data):
        tasks = AIHandler.analyze_content(c_type, data)
        self.after(0, lambda: self._post_process(tasks))

    def _post_process(self, tasks):
        if tasks:
            count = 0
            for t in tasks:
                self.task_manager.add_task(t)
                count += 1
            self.refresh_list()
            self.show_temp_message(f"AI 成功添加了 {count} 个任务")
            notification.notify(title='AI 待办助手', message=f'已提取 {count} 个任务', timeout=3)
        else:
            self.show_temp_message("AI 未能识别到有效任务")

    def monitor_clipboard(self):
        while True:
            try:
                img = ImageGrab.grabclipboard()
                if isinstance(img, Image.Image):
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    img_bytes = buf.getvalue()

                    curr_hash = hash(img_bytes)
                    if self.last_image_hash != curr_hash:
                        self.last_image_hash = curr_hash
                        self.after(0, lambda i=img: self.ask_to_analyze(i))
            except Exception as e:
                print(e)
            time.sleep(1.5)

    def ask_to_analyze(self, image):
        # 窗口唤醒
        self.deiconify()
        self.attributes('-topmost', 1)
        self.attributes('-topmost', 0)

        if messagebox.askyesno("发现新截图", "是否让 AI 分析这张截图中的待办事项？"):
            self.status_label.configure(text="正在上传并分析图片...", text_color="#1f6aa5")
            threading.Thread(target=self._process_api, args=("image", image), daemon=True).start()


if __name__ == "__main__":
    app = ModernTodoApp()
    app.mainloop()
