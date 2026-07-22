import React, { act } from "react";
import { createRoot } from "react-dom/client";
import Login from "./Login";


const mockNavigate = jest.fn();
const mockApiGet = jest.fn();
const mockGoogleRender = jest.fn(() => Promise.resolve());
let mockAuth;

jest.mock("react-router-dom", () => ({
  Link: ({ children, ...props }) => <a {...props}>{children}</a>,
  useNavigate: () => mockNavigate,
}), { virtual: true });
jest.mock("@/context/AuthContext", () => ({ useAuth: () => mockAuth }), { virtual: true });
jest.mock("./AuthLayout", () => ({ children }) => <div>{children}</div>);
jest.mock("@/components/ui/input", () => ({ Input: (props) => <input {...props} /> }), { virtual: true });
jest.mock("@/components/ui/checkbox", () => ({
  Checkbox: ({ onCheckedChange, ...props }) => (
    <input type="checkbox" onChange={(event) => onCheckedChange?.(event.target.checked)} {...props} />
  ),
}), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("lucide-react", () => ({ Eye: () => null, EyeOff: () => null }));
jest.mock("@/lib/googleAuth", () => ({
  getGoogleClientId: () => "",
  isGoogleConfigured: () => false,
  renderGoogleSignInButton: (...args) => mockGoogleRender(...args),
  setGoogleClientId: jest.fn(),
}), { virtual: true });
jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: { get: (...args) => mockApiGet(...args) },
}), { virtual: true });

const mockToast = require("sonner").toast;


function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}


describe("Login readiness regression", () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    mockNavigate.mockReset();
    mockToast.success.mockReset();
    mockToast.error.mockReset();
    mockApiGet.mockReset();
    mockGoogleRender.mockClear();
    mockAuth = {
      login: jest.fn(),
      googleSignIn: jest.fn(),
      formatApiError: (error) => error.message,
    };
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
  });

  test("keeps the Google Sign-In option visible while config is still loading", async () => {
    mockApiGet.mockReturnValue(new Promise(() => {}));

    await act(async () => root.render(<Login />));

    const googleButton = container.querySelector('button[data-testid="login-google"]');
    expect(googleButton).not.toBeNull();
    expect(googleButton.textContent).toContain("Continue with Google");
  });

  test("shows login failure and always resets the submitting state", async () => {
    mockApiGet.mockResolvedValue({ data: { enabled: false, client_id: "" } });
    const login = deferred();
    mockAuth.login.mockReturnValue(login.promise);

    await act(async () => root.render(<Login />));
    const form = container.querySelector('[data-testid="login-form"]');
    await act(async () => {
      form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    });
    expect(container.querySelector('[data-testid="login-submit"]').textContent).toBe("Signing in...");

    await act(async () => login.reject(new Error("Backend is unavailable. Please try again.")));

    expect(container.querySelector('[data-testid="login-submit"]').textContent).toBe("Sign in");
    expect(container.querySelector('[data-testid="login-submit"]').disabled).toBe(false);
    expect(container.querySelector('[data-testid="login-error"]').textContent).toContain("Please try again");
  });
});
