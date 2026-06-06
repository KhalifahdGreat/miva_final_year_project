import "./styles.css";
import { Widget, type WidgetOptions } from "./widget";

declare global {
  interface Window {
    SmeChatbot?: {
      init(options: WidgetOptions): Widget;
    };
  }
}

let instance: Widget | null = null;

window.SmeChatbot = {
  init(options: WidgetOptions): Widget {
    if (instance) return instance;
    instance = new Widget(options);
    return instance;
  },
};
