import React from "react";
import { render } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import { ToastProvider } from "../ToastContext";
import { AuthProvider } from "../AuthContext";
import { ServerProvider } from "../ServerContext";
import { ThemeProvider } from "../ThemeContext";
import { WebSocketProvider } from "../WebSocketContext";

const AllTheProviders = ({ children }) => {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <ThemeProvider>
            <WebSocketProvider>
              <ServerProvider>{children}</ServerProvider>
            </WebSocketProvider>
          </ThemeProvider>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
};

const customRender = (ui, options) =>
  render(ui, { wrapper: AllTheProviders, ...options });

export * from "@testing-library/react";
export { customRender as render };
