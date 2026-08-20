import json
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TOKEN_URL = "https://openapi.bazhuayu.com/token"


def request_token(username: str, password: str) -> dict:
    payload = json.dumps(
        {
            "username": username,
            "password": password,
            "grant_type": "password",
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            result = json.loads(raw)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(f"接口请求失败（HTTP {exc.code}）") from exc
    except URLError as exc:
        raise RuntimeError(f"网络连接失败：{exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError("请求超时，请检查网络后重试") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("接口返回的不是合法 JSON") from exc

    data = result.get("data")
    if isinstance(data, dict) and data.get("access_token"):
        return {
            "access_token": data["access_token"],
            "token_type": data.get("token_type") or "Bearer",
            "expires_in": data.get("expires_in"),
            "refresh_token": data.get("refresh_token"),
        }

    error = result.get("error")
    if isinstance(error, dict):
        message = error.get("message") or "账号或密码验证失败"
        request_id = result.get("requestId")
        if request_id:
            message = f"{message}\nrequestId：{request_id}"
        raise RuntimeError(message)

    raise RuntimeError(f"接口返回异常：{json.dumps(result, ensure_ascii=False)}")


class TokenTool(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("八爪鱼 Token 获取工具")
        self.geometry("700x460")
        self.minsize(620, 400)
        self.resizable(True, True)

        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.status = tk.StringVar(value="请输入八爪鱼账号和密码")
        self.token = ""

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=22)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(5, weight=1)

        ttk.Label(
            root,
            text="八爪鱼 Token 获取工具",
            font=("Microsoft YaHei UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(
            root,
            text="填写账号密码后点击“获取 Token”，无需安装 Python 或其他运行环境。",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 20))

        ttk.Label(root, text="八爪鱼账号：").grid(row=2, column=0, sticky="w", pady=6)
        username_entry = ttk.Entry(root, textvariable=self.username)
        username_entry.grid(row=2, column=1, columnspan=2, sticky="ew", pady=6)

        ttk.Label(root, text="八爪鱼密码：").grid(row=3, column=0, sticky="w", pady=6)
        password_entry = ttk.Entry(root, textvariable=self.password, show="*")
        password_entry.grid(row=3, column=1, sticky="ew", pady=6)
        self.show_password = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            root,
            text="显示密码",
            variable=self.show_password,
            command=lambda: password_entry.configure(
                show="" if self.show_password.get() else "*"
            ),
        ).grid(row=3, column=2, sticky="w", padx=(8, 0), pady=6)

        self.submit_button = ttk.Button(
            root,
            text="获取 Token",
            command=self._start_request,
        )
        self.submit_button.grid(row=4, column=0, sticky="w", pady=(14, 10))
        ttk.Label(root, textvariable=self.status).grid(
            row=4, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=(14, 10)
        )

        result_frame = ttk.LabelFrame(root, text="结果")
        result_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(6, 0))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(1, weight=1)

        self.result_label = ttk.Label(result_frame, text="尚未获取 Token")
        self.result_label.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 4))

        self.result_text = tk.Text(
            result_frame,
            height=8,
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
        )
        self.result_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

        self.copy_button = ttk.Button(
            result_frame,
            text="复制 Token",
            command=self._copy_token,
            state="disabled",
        )
        self.copy_button.grid(row=2, column=0, sticky="e", padx=12, pady=(4, 12))

        username_entry.focus_set()
        self.bind("<Return>", lambda _event: self._start_request())

    def _start_request(self) -> None:
        username = self.username.get().strip()
        password = self.password.get()
        if not username or not password:
            messagebox.showwarning("信息不完整", "请填写账号和密码。")
            return

        self.submit_button.configure(state="disabled")
        self.copy_button.configure(state="disabled")
        self.status.set("正在连接八爪鱼接口……")
        self._set_result("")
        threading.Thread(
            target=self._request_in_background,
            args=(username, password),
            daemon=True,
        ).start()

    def _request_in_background(self, username: str, password: str) -> None:
        try:
            result = request_token(username, password)
        except RuntimeError as exc:
            self.after(0, lambda: self._show_error(str(exc)))
            return
        self.after(0, lambda: self._show_success(result))

    def _show_success(self, result: dict) -> None:
        self.token = result["access_token"]
        expires_in = result.get("expires_in")
        expires_text = f"{expires_in} 秒" if expires_in else "接口未返回"
        text = (
            f"Authorization: {result['token_type']} {self.token}\n\n"
            f"Access Token:\n{self.token}"
        )
        self.status.set("获取成功")
        self.result_label.configure(text=f"Token 有效期：{expires_text}")
        self._set_result(text)
        self.copy_button.configure(state="normal")
        self.submit_button.configure(state="normal")

    def _show_error(self, message: str) -> None:
        self.status.set("获取失败")
        self.result_label.configure(text="请根据下方信息检查账号、密码或网络")
        self._set_result(message)
        self.submit_button.configure(state="normal")
        messagebox.showerror("获取 Token 失败", message)

    def _set_result(self, text: str) -> None:
        self.result_text.configure(state="normal")
        self.result_text.delete("1.0", "end")
        self.result_text.insert("1.0", text)
        self.result_text.configure(state="disabled")

    def _copy_token(self) -> None:
        if not self.token:
            return
        self.clipboard_clear()
        self.clipboard_append(self.token)
        self.update()
        self.status.set("Token 已复制到剪贴板")


if __name__ == "__main__":
    TokenTool().mainloop()
