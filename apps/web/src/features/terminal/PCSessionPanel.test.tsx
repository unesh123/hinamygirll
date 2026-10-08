import {render, screen, fireEvent, waitFor} from "@testing-library/react";
import {afterEach, beforeEach, expect, test, vi} from "vitest";
import {PCSessionPanel} from "./PCSessionPanel";
import {pcSessionToken} from "../../lib/remotePcSession";
beforeEach(() => {sessionStorage.clear(); vi.stubGlobal("location", {hostname: "hinaa.example"});});
afterEach(() => vi.unstubAllGlobals());
test("does not retain a rejected pairing code", async () => {
 vi.stubGlobal("fetch", vi.fn(async () => ({ok:true, json:async () => ({execution_allowed:false})})));
 render(<PCSessionPanel onChanged={vi.fn()}/>);
 fireEvent.click(screen.getByText("PC connection"));
 fireEvent.change(screen.getByLabelText("Private PC pairing code"), {target:{value:"x".repeat(50)}});
 fireEvent.click(screen.getByText("Connect PC for this session"));
 await screen.findByText("Pairing code expired or does not match your signed-in owner account.");
 expect(pcSessionToken()).toBe("");
});
test("retains verified pairing and clears it on disconnect", async () => {
 vi.stubGlobal("fetch", vi.fn(async () => ({ok:true, json:async () => ({execution_allowed:true})})));
 render(<PCSessionPanel onChanged={vi.fn()}/>);
 fireEvent.click(screen.getByText("PC connection"));
 fireEvent.change(screen.getByLabelText("Private PC pairing code"), {target:{value:"x".repeat(50)}});
 fireEvent.click(screen.getByText("Connect PC for this session"));
 await screen.findByText("PC session connected. Access expires automatically.");
 expect(pcSessionToken()).toBe("x".repeat(50));
 fireEvent.click(screen.getByText("Disconnect PC"));
 await waitFor(() => expect(pcSessionToken()).toBe(""));
});
