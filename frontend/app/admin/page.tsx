"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type User={user_id:string;email:string;role:string;email_verified:boolean;two_factor_enabled:boolean};
type Role={name:string;permissions:string[];description?:string};
type Status={status:string;exchange:string;trade_date?:string|null;records_seen?:number;records_missing_core_prices?:number;fetched_at?:string|null};
type Pipeline={scheduler_enabled:boolean;scheduler_running:boolean;sources:Record<string,boolean>;recent_runs:Record<string,unknown>[];checked_at:string};

export default function AdminPage(){
  const [users,setUsers]=useState<User[]>([]); const [roles,setRoles]=useState<Role[]>([]); const [statuses,setStatuses]=useState<Status[]>([]); const [pipeline,setPipeline]=useState<Pipeline|null>(null);
  const [roleDraft,setRoleDraft]=useState<Record<string,string>>({}); const [exchange,setExchange]=useState<"NSE"|"BSE">("NSE"); const [file,setFile]=useState<File|null>(null);
  const [message,setMessage]=useState(""); const [error,setError]=useState(""); const [running,setRunning]=useState(false);\n  const [contextKind,setContextKind]=useState<"sector"|"institutional"|"event">("sector"); const [contextFile,setContextFile]=useState<File|null>(null);

  async function load(){
    try{
      const [u,r,p]=await Promise.all([
        apiFetch<{users:User[]}>("/api/v1/admin/users"),
        apiFetch<{roles:Role[]}>("/api/v1/admin/roles"),
        apiFetch<Pipeline>("/api/v1/admin/data-pipeline/status")
      ]);
      setUsers(u.users);setRoles(r.roles);setPipeline(p);
      const s=await Promise.all(["NSE","BSE"].map(x=>apiFetch<Status>("/api/v1/market/eod/status?exchange="+x)));setStatuses(s);
    }catch(err){setError(err instanceof Error?err.message:"Admin access denied");}
  }
  useEffect(()=>{load()},[]);

  async function updateRole(user_id:string){
    const role=roleDraft[user_id];if(!role)return;
    try{await apiFetch("/api/v1/admin/users/"+user_id+"/role",{method:"PATCH",body:JSON.stringify({role})});setMessage("User role updated.");await load();}
    catch(err){setError(err instanceof Error?err.message:"Unable to update role");}
  }

  async function ingest(event:FormEvent){
    event.preventDefault();setMessage("");setError("");
    if(!file){setError("Choose an NSE/BSE EOD CSV or ZIP file.");return;}
    const body=new FormData();body.append("file",file);
    try{const result=await apiFetch<{trade_date:string;records_seen:number}>("/api/v1/market/eod/ingest?exchange="+exchange,{method:"POST",body});setMessage(exchange+" EOD ingested for "+result.trade_date+" ("+result.records_seen+" records).");setFile(null);await load();}
    catch(err){setError(err instanceof Error?err.message:"EOD ingestion failed");}
  }

  async function ingestContext(event:FormEvent){
    event.preventDefault();setError("");setMessage("");
    if(!contextFile){setError("Choose a context CSV file.");return;}
    const body=new FormData();body.append("file",contextFile);
    try{const result=await apiFetch<{dataset:string;records_seen:number}>("/api/v1/market/context/ingest/"+contextKind,{method:"POST",body});setMessage(contextKind+" context ingested ("+result.records_seen+" rows).");setContextFile(null);}
    catch(err){setError(err instanceof Error?err.message:"Context ingestion failed");}
  }

  async function runPipeline(){
    setRunning(true);setError("");setMessage("");
    try{const result=await apiFetch<{trade_date:string}>("/api/v1/admin/data-pipeline/run",{method:"POST"});setMessage("Pipeline run completed for "+result.trade_date+".");await load();}
    catch(err){setError(err instanceof Error?err.message:"Pipeline run failed");}finally{setRunning(false);}
  }

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">Admin</div><h1>Platform administration</h1><p className="lead">Users, roles, security audit and automated market-data pipeline control.</p></div></section>
    {error&&<div className="error">{error}</div>}{message&&<div className="panel" style={{marginBottom:18}}>{message}</div>}

    <section className="panel"><div className="section-title"><div><div className="eyebrow">Automation</div><h2>EOD pipeline</h2></div><button className="button primary" onClick={runPipeline} disabled={running}>{running?"Running...":"Run pipeline now"}</button></div>
      <div className="stats-row"><span>Scheduler: {pipeline?.scheduler_running?"Running":"Stopped"}</span><span>Enabled: {pipeline?.scheduler_enabled?"Yes":"No"}</span><span>NSE EOD: {pipeline?.sources.NSE_EOD?"Configured":"Not configured"}</span><span>BSE EOD: {pipeline?.sources.BSE_EOD?"Configured":"Not configured"}</span><span>NSE Index: {pipeline?.sources.NSE_INDEX?"Configured":"Not configured"}</span><span>BSE Index: {pipeline?.sources.BSE_INDEX?"Configured":"Not configured"}</span></div>
    </section>

    <section className="panel" style={{marginTop:18}}><div className="eyebrow">Data Pipeline</div><h2>Manual EOD upload</h2><p className="muted">Upload an official EOD CSV/ZIP when an exchange source template is not configured or an exceptional re-run is required.</p>
      <form onSubmit={ingest}><div className="actions"><select value={exchange} onChange={e=>setExchange(e.target.value as "NSE"|"BSE")}><option>NSE</option><option>BSE</option></select><input type="file" accept=".csv,.zip,.txt" onChange={e=>setFile(e.target.files?.[0]??null)}/><button className="button primary">Ingest EOD</button></div></form>
      <div className="table-wrap" style={{marginTop:14}}><table><thead><tr><th>Exchange</th><th>Status</th><th>Trade Date</th><th>Records</th><th>Fetched</th></tr></thead><tbody>{statuses.map(s=><tr key={s.exchange}><td>{s.exchange}</td><td>{s.status}</td><td>{s.trade_date??"--"}</td><td>{s.records_seen??"--"}</td><td>{s.fetched_at?new Date(s.fetched_at).toLocaleString():"--"}</td></tr>)}</tbody></table></div>
    </section>

    <section className="panel" style={{marginTop:18}}><div className="eyebrow">Intelligence Context</div><h2>Sector / Institutional / Event data</h2><p className="muted">Upload source data separately so EOD Intelligence can join it with the market session.</p><form onSubmit={ingestContext}><div className="actions"><select value={contextKind} onChange={e=>setContextKind(e.target.value as "sector"|"institutional"|"event")}><option value="sector">Sector mapping</option><option value="institutional">FII/FPI + DII</option><option value="event">Corporate events</option></select><input type="file" accept=".csv,.txt" onChange={e=>setContextFile(e.target.files?.[0]??null)}/><button className="button primary">Ingest context</button></div></form></section>

    <section className="panel" style={{marginTop:18}}><div className="eyebrow">RBAC</div><h2>Users and roles</h2><div className="caption">{roles.length} roles configured</div>
      <div className="table-wrap" style={{marginTop:12}}><table><thead><tr><th>Email</th><th>Role</th><th>Verified</th><th>2FA</th><th>Action</th></tr></thead><tbody>{users.map(user=><tr key={user.user_id}><td>{user.email}</td><td><select value={roleDraft[user.user_id]??user.role} onChange={e=>setRoleDraft(d=>({...d,[user.user_id]:e.target.value}))}>{roles.map(role=><option value={role.name} key={role.name}>{role.name}</option>)}</select></td><td>{user.email_verified?"Yes":"No"}</td><td>{user.two_factor_enabled?"On":"Off"}</td><td><button className="button" onClick={()=>updateRole(user.user_id)}>Update</button></td></tr>)}</tbody></table></div>
    </section>
  </AppShell>;
}
