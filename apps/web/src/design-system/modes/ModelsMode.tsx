import { useMemo, useState } from "react";
import { Cpu, Search, RefreshCw, Sparkles, Check } from "lucide-react";
import { useCapabilities } from "../../features/providers/hooks/useCapabilities";
import { providerModeFromId } from "../../features/providers/utils/providerLabels";
import "./modelsMode.css";

interface Props {
  isDark?: boolean;
  selectedModelId?: string | null;
  selectedProviderId?: string | null;
  onSelectModel: (modelId:string, providerId:string) => void;
  onSelectAuto: () => void;
}

export function ModelsMode({isDark=false, selectedModelId, selectedProviderId, onSelectModel, onSelectAuto}:Props) {
  const {models,providers,runtime,loading,error,refetch} = useCapabilities();
  const [query,setQuery] = useState("");
  const [providerFilter,setProviderFilter] = useState("all");
  const visible = useMemo(() => models.filter(model => {
    const provider = providers.find(item => item.id===model.provider);
    return (providerFilter==="all" || model.provider===providerFilter) &&
      `${model.name} ${model.id} ${provider?.name ?? model.provider}`.toLowerCase().includes(query.trim().toLowerCase());
  }),[models,providers,providerFilter,query]);
  const configured = providers.filter(provider => provider.configured).length;
  const verified = providers.filter(provider => provider.health==="healthy").length;
  return <section className={`models-mode${isDark ? " models-mode--dark" : ""}`} aria-label="Models and providers">
    <header className="models-mode__header">
      <div><p className="models-mode__eyebrow"><Cpu size={13}/> INTELLIGENCE LIBRARY</p><h1>Models &amp; providers</h1><p>Choose a brain for your next conversation. Live health comes from actual provider calls.</p></div>
      <button type="button" className="models-mode__refresh" onClick={() => void refetch()} aria-label="Refresh model catalog"><RefreshCw size={15}/><span>Refresh</span></button>
    </header>
    <div className="models-mode__summary"><span><strong>{models.length}</strong> models</span><span><strong>{configured}</strong> configured providers</span><span><strong>{verified}</strong> verified healthy</span></div>
    <button type="button" className="models-mode__auto" aria-pressed={!selectedModelId} onClick={onSelectAuto}><Sparkles size={18}/><span><strong>Let Hina choose</strong><small>Automatic routing through your available providers</small></span>{!selectedModelId && <Check size={16}/>}</button>
    <div className="models-mode__filters"><label><Search size={15}/><input aria-label="Search models" placeholder="Search models or providers…" value={query} onChange={event=>setQuery(event.target.value)}/></label><select aria-label="Filter models by provider" value={providerFilter} onChange={event=>setProviderFilter(event.target.value)}><option value="all">All providers</option>{providers.map(provider=><option key={provider.id} value={provider.id}>{provider.name}</option>)}</select></div>
    {error && <p role="alert" className="models-mode__error">{error} <button type="button" onClick={()=>void refetch()}>Retry</button></p>}
    {loading && models.length===0 ? <p role="status">Loading your model library…</p> : visible.length===0 ? <p className="models-mode__empty">{runtime.backendConnected ? "No models match your search." : "Connect to the workspace to load your models."}</p> : <div className="models-mode__grid">
      {visible.map(model=>{
        const provider = providers.find(item=>item.id===model.provider);
        const health = provider?.health ?? "untested";
        const supported = providerModeFromId(model.provider)!==null;
        const canSelect = runtime.backendConnected && Boolean(provider?.configured) && model.configured && health!=="unavailable" && supported;
        const selected = selectedModelId===model.id && providerModeFromId(selectedProviderId ?? "")===providerModeFromId(model.provider);
        const status = !provider?.configured ? "Setup required" : health==="healthy" ? "Verified healthy" : health==="unavailable" ? "Unavailable" : health==="degraded" ? "Last call failed" : "Not yet tested";
        return <button key={`${model.provider}:${model.id}`} type="button" className="models-mode__model" disabled={!canSelect} aria-pressed={selected} aria-label={`Use ${model.name} via ${provider?.name ?? model.provider}`} onClick={()=>onSelectModel(model.id,model.provider)} title={provider?.healthMessage || (!supported ? "This provider has no supported chat route." : model.description)}>
          <span className="models-mode__provider">{provider?.name ?? model.provider}{selected && <Check size={13}/>}</span><strong>{model.name}</strong><small>{model.description || model.id}</small><span className="models-mode__health" data-health={health}>{status}</span>
        </button>;
      })}
    </div>}
  </section>;
}
