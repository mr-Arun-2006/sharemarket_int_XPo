"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type User={user_id:string;email:string;role:string;email_verified:boolean;two_factor_enabled:boolean};
type Role={name:string;permissions:string[];description?:string};
type Status={status:string;exchange:string;trade_date?:string|null;records_seen?:number;records_missing_core_prices?:number;fetched_at?:string|null};

export default function AdminPage(){
  const [users,setUsers]=useState<User[]>([]);
  const [roles,setRoles]=useState<Role[]>([]);
  const [statuses,setStatuses]=useState<Status[]>([]);
  const [roleDraft,setRoleDraft]=useState<Record<string,string>>({});
  const [exchange,setExchange]=useState<"NSE"|"BSE">("NSE");
  const [file,setFile]=useState<File|null>(null);
  const [message,setMessage]=useState("");
  const [error,setError]=useState("");

  async function load(){
    try{
      const [u,r]=await Promise.all([
        apiFetch<{users:User[]}>("/api/v1/admin/users"),
        apiFetch<{roles:Role[]}>("/api/v1/admin/roles")
      ]);
      setUsers(u.users); setRoles(r.roles);
      const s=await Promise.all(["NSE","BSE"].map(x=>apiFetch<Status>("/api/v1/market/eod/status?exchange="+x)));
      setStatuses(s);
    }catch(err){setError(err instanceof Error?err.message:"Admin access denied");}
  }
  useEffect(()=>{load()},[]);

  async function updateRole(user_id:string){
    const role=roleDraft[user_id]; if(!role) return;
    try{await apiFetch("/api/v1/admin/users/"+user_id+"/role",{method:"PATCH",body:JSON.stringify({role})});setMessage("User role updated.");await load();}
    catch(err){setError(err instanceof Error?err.message:"Unable to update role");}
  }

  async function ingest(event:FormEvent){
    event.preventDefault(); setMessage(""); setError("");
    if(!file){setError("Choose an NSE/BSE EOD CSV or ZIP file.");return;}
    const body=new FormData(); body.append("file",file);
    try{
      const result=await apiFetch<{trade_date:string;records_seen:number;status:string}>("/api/v1/market/eod/ingest?exchange="+exchange,{method:"POST",body});
      setMessage(exchange+" EOD ingested for "+result.trade_date+" ("+result.records_seen+" records).");
      setFile(null); await load();
    }catch(err){setError(err instanceof Error?err.message:"EOD ingestion failed");}
  }

  return <AppShell>
    <section className="page-heading"><div><div className="eyebrow">Admin</div><h1>Platform administration</h1><p className="lead">Users, roles, security audit and exchange data ingestion.</p></div></section>
    {error&&<div className="error">{error}</div>}{message&&<div className="panel" style={{marginBottom:18}}>{message}</div>}

    <section className="panel"><div className="eyebrow">Data Pipeline</div><h2>Ingest official EOD file</h2><p className="muted">Upload a normalized NSE or BSE EOD CSV/ZIP. Existing rows for the same exchange and trade date are replaced atomically at the dataset level.</p>
      <form onSubmit={ingest}><div className="actions"><select value={exchange} onChange={e=>setExchange(e.target.value as "NSE"|"BSE")}><option>NSE</option><option>BSE</option></select><input type="file" accept=".csv,.zip,.txt" onChange={e=>setFile(e.target.files?.[0]??null)}/><button className="button primary">Ingest EOD</button></div></form>
      <div className="table-wrap" style={{marginTop:14}}><table><thead><tr><th>Exchange</th><th>Status</th><th>Trade Date</th><th>Records</th><th>Fetched</th></tr></thead><tbody>{statuses.map(s=><tr key={s.exchange}><td>{s.exchange}</td><td>{s.status}</td><td>{s.trade_date??"--"}</td><td>{s.records_seen??"--"}</td><td>{s.fetched_at?new Date(s.fetched_at).toLocaleString():"--"}</td></tr>)}</tbody></table></div>
    </section>

    <section className="panel" style={{marginTop:18}}><div className="eyebrow">RBAC</div><h2>Users and roles</h2><div className="caption">{roles.length} roles configured</div>
      <div className="table-wrap" style={{marginTop:12}}><table><thead><tr><th>Email</th><th>Role</th><th>Verified</th><th>2FA</th><th>Action</th></tr></thead><tbody>
        {users.map(user=><tr key={user.user_id}><td>{user.email}</td><td><select value={roleDraft[user.user_id]??user.role} onChange={e=>setRoleDraft(d=>({...d,[user.user_id]:e.target.value}))}>{roles.map(role=><option value={role.name} key={role.name}>{role.name}</option>)}</select></td><td>{user.email_verified?"Yes":"No"}</td><td>{user.two_factor_enabled?"On":"Off"}</td><td><button className="button" onClick={()=>updateRole(user.user_id)}>Update</button></td></tr>)}
      </tbody></table></div>
    </section>
  </AppShell>;
}
