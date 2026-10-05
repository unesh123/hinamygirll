import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import { ClerkSessionGate } from "./ClerkSessionGate";
const session = vi.hoisted(() => ({loaded:true,signed:false,getToken:vi.fn(),signOut:vi.fn()}));
vi.mock("@clerk/react", () => ({
  useAuth: () => ({isLoaded:session.loaded,isSignedIn:session.signed,getToken:session.getToken}),
  useClerk: () => ({signOut:session.signOut}),
  SignInButton: ({children}: {children:unknown}) => children,
}));
vi.mock("../../App", () => ({default:() => <div>Authenticated workspace</div>,ClerkFetchInterceptor:()=>null}));
vi.mock("../../components/ui/AvatarPresence", () => ({AvatarPresence:()=> <div>Hina portrait</div>}));

describe("Private Hina session gate", () => {
  beforeEach(() => { session.loaded=true; session.signed=false; session.getToken.mockReset().mockResolvedValue("test-session"); session.signOut.mockReset(); });
  afterEach(() => vi.unstubAllGlobals());
  it("shows Hina and a real connection before sign-in", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({service:"hinaa-api",status:"ok"}))));
    render(<ClerkSessionGate />);
    expect(screen.getByRole("button",{name:"Enter your workspace"})).toBeInTheDocument();
    await screen.findByText("Hina’s workspace is connected");
    expect(screen.queryByText("Authenticated workspace")).not.toBeInTheDocument();
  });
  it("does not mount private features until owner verification succeeds", async () => {
    session.signed=true;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({authenticated:true,authMode:"clerk"}))));
    render(<ClerkSessionGate />);
    await screen.findByText("Authenticated workspace");
    expect(fetch).toHaveBeenCalledWith("/api/v1/auth/session", expect.objectContaining({headers:{Authorization:"Bearer test-session"}}));
  });
  it("keeps an authenticated non-owner outside the workspace and offers account switching", async () => {
    session.signed=true;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("",{status:403})));
    render(<ClerkSessionGate />);
    await screen.findByText(/This account does not have owner access/);
    expect(screen.queryByText("Authenticated workspace")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"Switch account"}));
    expect(session.signOut).toHaveBeenCalledOnce();
  });
  it("offers retry after a backend failure without opening private features", async () => {
    session.signed=true;
    const request=vi.fn().mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(new Response(JSON.stringify({authenticated:true})));
    vi.stubGlobal("fetch",request);
    render(<ClerkSessionGate />);
    await waitFor(() => expect(screen.getByRole("button",{name:"Retry workspace access"})).toBeEnabled());
    expect(screen.queryByText("Authenticated workspace")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"Retry workspace access"}));
    await screen.findByText("Authenticated workspace");
  });
});
