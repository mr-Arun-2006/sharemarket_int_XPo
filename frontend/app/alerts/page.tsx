"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type Alert={alert_id:string;name:string;alert_type:string;exchange:string;symbol:string;operator:string;threshold:number|null;indicator?:string|null;channel:string;cooldown_minutes:number;enabled:boolean;created_at:string;last_triggered_at?:string|null};
type Event={event_id:string;alert_name:string;alert_type:string;symbol:string;value:number|null;threshold:number|null;operator:string;triggered_at:string;channel:string};

const types=["price","percent_change","volume","technical","ai_event","sentiment","regime"];

export default function AlertsPage(){
  const [alerts,setAlerts]=useState<Alert[]>([]); const [events,setEvents]=useState<Event[]>([]);
  const [name,setName]=useState(""); const [symbol,setSymbol]=useState(""); const [type,setType]=useState("price"); const [op,setOp]=useState(">="); const [threshold,setThreshold]=useState(""); const [channel,setChannel]=useState("in_app");
  const [error,setError]=useState(""); const [message,setMessage]=useState("");

  async function load(){
    try{
      const [a,e]=await Promise.all([apiFetch<{alerts:Alert[]}>("/api/v1/alerts"),apiFetch<{events:Event[]}>("/api/v1/alerts/events?limit=50")]);
      setAlerts(a.alerts);setEvents(e.events);
    }catch(err){setError(err instanceof Error?err.message:"Unable to load alerts");}
  }
  useEffect(()=>{load()},[]);

  async function create(event:FormEvent){
    event.preventDefault();setError("");setMessage("");
    try{
      await apiFetch("/api/v1/alerts",{method:"POST",body:JSON.stringify({name,alert_type:type,exchange:"NSE",symbol:symbol.toUpperCase(),operator:op,threshold:threshold===""?null:Number(threshold),channel,cooldown_minutes:5})});
      setName("");setSymbol("");setThreshold("");setMessage("Alert created.");await load();
    }catch(err){setError(err instanceof Error?err.message:"Unable to create alert");}
  }
  async function toggle(a:Alert){
    try{await apiFetch("/api/v1/alerts/"+a.alert_id,{method:"PATCH",body:JSON.stringify({enabled:!a.enabled})});await load();}
    catch(err){setError(err instanceof Error?err.message:"Unable to update alert");}
  }
  async function remove(id:string){
    try{await apiFetch("/api/v1/alerts/"+id,{method:"DELETE"});await load();}
    catch(err){setError(err instanceof Error?err.message:"Unable to delete alert");}
  }

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">Alerts</div><h1>Alerts center</h1><p className="lead">Create and manage price, volume, technical, AI-event, sentiment and regime alert rules. Live price, change and volume rules are evaluated from WebSocket ticks.</p></div></section>
    {error&&<div className="error">{error}</div>}{message&&<div className="panel" style={{marginBottom:18}}>{message}</div>}

    <section className="panel" id="create"><div className="eyebrow">Create Alert</div><h2>New alert rule</h2>
      <form onSubmit={create}><div className="grid-2">
        <input value={name} onChange={e=>setName(e.target.value)} placeholder="Alert name" required/>
        <input value={symbol} onChange={e=>setSymbol(e.target.value)} placeholder="NSE symbol" required/>
        <select value={type} onChange={e=>setType(e.target.value)}>{types.map(x=><option key={x}>{x}</option>)}</select>
        <select value={op} onChange={e=>setOp(e.target.value)}><option>{">="}</option><option>{">"}</option><option>{"<="}</option><option>{"<"}</option><option>{"=="}</option></select>
        <input value={threshold} onChange={e=>setThreshold(e.target.value)} type="number" step="any" placeholder="Threshold"/>
        <select value={channel} onChange={e=>setChannel(e.target.value)}><option value="in_app">In-app</option><option value="email">Email</option><option value="both">In-app + Email</option></select>
      </div><div className="actions"><button className="button primary">Create Alert</button></div></form>
    </section>

    <section className="panel" style={{marginTop:18}}><div className="section-title"><div><div className="eyebrow">Active Rules</div><h2>Configured alerts</h2></div><span className="caption">{alerts.length} rules</span></div>
      <div className="table-wrap"><table><thead><tr><th>Name</th><th>Type</th><th>Symbol</th><th>Condition</th><th>Channel</th><th>Status</th><th>Actions</th></tr></thead><tbody>
        {alerts.map(a=><tr key={a.alert_id}><td>{a.name}</td><td>{a.alert_type}</td><td>{a.exchange}:{a.symbol}</td><td>{a.operator} {a.threshold??"--"}</td><td>{a.channel}</td><td>{a.enabled?"Active":"Paused"}</td><td><button className="button" onClick={()=>toggle(a)}>{a.enabled?"Pause":"Enable"}</button>{" "}<button className="button" onClick={()=>remove(a.alert_id)}>Delete</button></td></tr>)}
        {alerts.length===0&&<tr><td colSpan={7}>No alerts configured yet.</td></tr>}
      </tbody></table></div>
    </section>

    <section className="panel" style={{marginTop:18}}><div className="eyebrow">Alert History</div><h2>Triggered events</h2>
      <div className="table-wrap"><table><thead><tr><th>Alert</th><th>Type</th><th>Symbol</th><th>Observed</th><th>Condition</th><th>Time</th></tr></thead><tbody>
        {events.map(e=><tr key={e.event_id}><td>{e.alert_name}</td><td>{e.alert_type}</td><td>{e.symbol}</td><td>{e.value??"--"}</td><td>{e.operator} {e.threshold??"--"}</td><td>{new Date(e.triggered_at).toLocaleString()}</td></tr>)}
        {events.length===0&&<tr><td colSpan={6}>No triggered events yet.</td></tr>}
      </tbody></table></div>
    </section>
  </AppShell>;
}
