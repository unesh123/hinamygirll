import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ModelsMode } from "./ModelsMode";

const { capabilities } = vi.hoisted(() => ({ capabilities: vi.fn() }));
vi.mock("../../features/providers/hooks/useCapabilities", () => ({useCapabilities: capabilities}));
const select = vi.fn();
const auto = vi.fn();
const provider = (id:string, configured=true, health="healthy") => ({id,name:id,configured,health});
const model = (provider:string,id="shared-model") => ({id,name:`${provider} model`,provider,configured:true,description:"Chat model"});
beforeEach(() => {
  vi.clearAllMocks();
  capabilities.mockReturnValue({models:[model("xkiro"),model("apmix"),model("openai"),model("ollama"),model("unsupported")],providers:[provider("xkiro"),provider("apmix"),provider("openai",false),provider("ollama",true,"unavailable"),provider("unsupported")],runtime:{backendConnected:true},loading:false,error:null,refetch:vi.fn()});
});
describe("ModelsMode", () => {
  it("keeps identical model IDs qualified by provider when selecting and highlighting", () => {
    render(<ModelsMode selectedModelId="shared-model" selectedProviderId="xkiro" onSelectModel={select} onSelectAuto={auto}/>);
    expect(screen.getByRole("button",{name:"Use xkiro model via xkiro"})).toHaveAttribute("aria-pressed","true");
    const other=screen.getByRole("button",{name:"Use apmix model via apmix"});
    expect(other).toHaveAttribute("aria-pressed","false");
    fireEvent.click(other);
    expect(select).toHaveBeenCalledWith("shared-model","apmix");
  });
  it("disables missing credentials, unavailable services, and unsupported chat routes", () => {
    render(<ModelsMode onSelectModel={select} onSelectAuto={auto}/>);
    for(const id of ["openai","ollama","unsupported"]) expect(screen.getByRole("button",{name:`Use ${id} model via ${id}`})).toBeDisabled();
    expect(screen.getByRole("button",{name:"Use xkiro model via xkiro"})).toBeEnabled();
  });
  it("filters models by both provider and search and offers automatic routing", () => {
    render(<ModelsMode onSelectModel={select} onSelectAuto={auto}/>);
    fireEvent.change(screen.getByLabelText("Filter models by provider"),{target:{value:"apmix"}});
    expect(screen.queryByRole("button",{name:"Use xkiro model via xkiro"})).not.toBeInTheDocument();
    expect(screen.getByRole("button",{name:"Use apmix model via apmix"})).toBeVisible();
    fireEvent.change(screen.getByLabelText("Search models"),{target:{value:"missing"}});
    expect(screen.getByText("No models match your search.")).toBeVisible();
    fireEvent.click(screen.getByRole("button",{name:/Let Hina choose/}));
    expect(auto).toHaveBeenCalledOnce();
  });
  it("blocks selections while the backend is disconnected", () => {
    capabilities.mockReturnValue({...capabilities(),runtime:{backendConnected:false}});
    render(<ModelsMode onSelectModel={select} onSelectAuto={auto}/>);
    expect(screen.getByRole("button",{name:"Use xkiro model via xkiro"})).toBeDisabled();
  });
});
