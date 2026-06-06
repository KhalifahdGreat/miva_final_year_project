/* eslint-disable @typescript-eslint/no-explicit-any */

export interface WidgetOptions {
  apiBase: string;
  widgetKey: string;
  title?: string;
  subtitle?: string;
}

type Role = "user" | "bot" | "system";

interface SessionState {
  token: string;
  expiresAt: string;
}

export class Widget {
  private readonly opts: Required<WidgetOptions>;
  private readonly launcher: HTMLButtonElement;
  private readonly panel: HTMLDivElement;
  private readonly body: HTMLDivElement;
  private readonly input: HTMLInputElement;
  private readonly sendBtn: HTMLButtonElement;
  private session: SessionState | null = null;
  private sending = false;

  constructor(options: WidgetOptions) {
    this.opts = {
      apiBase: options.apiBase.replace(/\/$/, ""),
      widgetKey: options.widgetKey,
      title: options.title ?? "Customer support",
      subtitle: options.subtitle ?? "We typically reply in minutes",
    };

    this.launcher = this.buildLauncher();
    this.panel = this.buildPanel();
    this.body = this.panel.querySelector(".smec-body") as HTMLDivElement;
    this.input = this.panel.querySelector(".smec-input") as HTMLInputElement;
    this.sendBtn = this.panel.querySelector(".smec-send") as HTMLButtonElement;

    document.body.appendChild(this.launcher);
    document.body.appendChild(this.panel);

    this.launcher.addEventListener("click", () => this.toggle());
    (this.panel.querySelector(".smec-close") as HTMLElement).addEventListener(
      "click",
      () => this.toggle(false),
    );
    this.sendBtn.addEventListener("click", () => this.handleSend());
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.handleSend();
      }
    });
  }

  // ----------------------------------------------------------------------
  // UI helpers
  // ----------------------------------------------------------------------

  private buildLauncher(): HTMLButtonElement {
    const btn = document.createElement("button");
    btn.className = "smec-launcher";
    btn.setAttribute("aria-label", "Open chat");
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" aria-hidden="true">' +
      '<path d="M12 3C6.48 3 2 6.94 2 11.7c0 2.18.99 4.17 2.64 5.66L4 21l4.05-1.55c1.23.42 2.55.65 3.95.65 5.52 0 10-3.94 10-8.7S17.52 3 12 3z"/>' +
      "</svg>";
    return btn;
  }

  private buildPanel(): HTMLDivElement {
    const panel = document.createElement("div");
    panel.className = "smec-panel";
    panel.innerHTML = `
      <div class="smec-header">
        <div>
          <div class="smec-title">${escape(this.opts.title)}</div>
          <div class="smec-subtitle">${escape(this.opts.subtitle)}</div>
        </div>
        <button class="smec-close" aria-label="Close chat">×</button>
      </div>
      <div class="smec-body" role="log" aria-live="polite"></div>
      <div class="smec-footer">
        <input class="smec-input" type="text" placeholder="Type a message..." />
        <button class="smec-send">Send</button>
      </div>
    `;
    return panel;
  }

  private toggle(force?: boolean): void {
    const open = force ?? !this.panel.classList.contains("smec-open");
    this.panel.classList.toggle("smec-open", open);
    if (open && !this.session) {
      void this.openSession();
    }
    if (open) {
      this.input.focus();
    }
  }

  private addMessage(role: Role, text: string): void {
    const div = document.createElement("div");
    div.className = `smec-msg smec-msg-${role}`;
    div.textContent = text;
    this.body.appendChild(div);
    this.scrollToEnd();
  }

  private addTyping(): HTMLElement {
    const div = document.createElement("div");
    div.className = "smec-typing";
    div.innerHTML = "<span></span><span></span><span></span>";
    this.body.appendChild(div);
    this.scrollToEnd();
    return div;
  }

  private scrollToEnd(): void {
    this.body.scrollTop = this.body.scrollHeight;
  }

  // ----------------------------------------------------------------------
  // Network
  // ----------------------------------------------------------------------

  private async openSession(): Promise<void> {
    try {
      const res = await fetch(`${this.opts.apiBase}/widget/v1/session`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ widget_key: this.opts.widgetKey }),
      });
      if (!res.ok) {
        throw new Error(`session failed (${res.status})`);
      }
      const data: { session_token: string; expires_at: string; greeting: string } =
        await res.json();
      this.session = { token: data.session_token, expiresAt: data.expires_at };
      if (data.greeting) {
        this.addMessage("bot", data.greeting);
      }
    } catch (err) {
      this.addMessage("system", `Couldn't open chat session: ${String(err)}`);
    }
  }

  private async handleSend(): Promise<void> {
    if (this.sending) return;
    const text = this.input.value.trim();
    if (!text) return;
    if (!this.session) {
      await this.openSession();
      if (!this.session) return;
    }
    this.input.value = "";
    this.addMessage("user", text);
    this.sending = true;
    this.sendBtn.disabled = true;
    const typing = this.addTyping();

    try {
      const res = await fetch(`${this.opts.apiBase}/widget/v1/message`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${this.session.token}`,
        },
        body: JSON.stringify({ text }),
      });
      typing.remove();
      if (!res.ok) {
        throw new Error(`message failed (${res.status})`);
      }
      const data: { reply: string; escalated: boolean } = await res.json();
      this.addMessage("bot", data.reply);
      if (data.escalated) {
        this.addMessage("system", "A colleague will follow up shortly.");
      }
    } catch (err) {
      typing.remove();
      this.addMessage("system", `Network hiccup: ${String(err)}`);
    } finally {
      this.sending = false;
      this.sendBtn.disabled = false;
      this.input.focus();
    }
  }
}

function escape(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
