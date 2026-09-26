"use client";

import { useEffect, useState } from "react";
import { AppShell } from "../../components/AppShell";
import { apiFetch } from "../../lib/api";

type User = {user_id:string;email:string;role:string;email_verified:boolean;two_factor_enabled:boolean};

export default function AdminPage() {
  const [users,setUsers]=useState<User[]>([]);
  const [error,setError]=useState("");
  const [roleDraft,setRoleDraft]=useState<Record<string,string>>({});

  async function load() {
    try { setUsers((await apiFetch<{users:User[]}>("/api/v1/admin/users")).users); }
    catch (err) { setError(err instanceof Error ? err.message : "Admin access denied"); }
  }
  useEffect(()=>{load()},[]);

  async function updateRole(user_id:string) {
    const role=roleDraft[user_id];
    if (!role) return;
    try { await apiFetch(`/api/v1/admin/users/${user_id}/role`,{method:"PATCH",body:JSON.stringify({role})}); await load(); }
    catch(err){setError(err instanceof Error ? err.message : "Unable to update role");}
  }

  return <AppShell><section className="page-heading"><div><div className="eyebrow">Admin</div><h1>Platform administration</h1><p className="lead">Users, roles, permissions and security audit events.</p></div></section><section className="panel"><h2>Users</h2>{error&&<div className="error">{error}</div>}<div className="table-wrap"><table><thead><tr><th>Email</th><th>Role</th><th>Verified</th><th>2FA</th><th>Action</th></tr></thead><tbody>{users.map(user=><tr key={user.user_id}><td>{user.email}</td><td><select value={roleDraft[user.user_id] ?? user.role} onChange={e=>setRoleDraft(d=>({...d,[user.user_id]:e.target.value}))}><option value="user">user</option><option value="analyst">analyst</option><option value="admin">admin</option></select></td><td>{user.email_verified ? "Yes":"No"}</td><td>{user.two_factor_enabled ? "On":"Off"}</td><td><button className="button" onClick={()=>updateRole(user.user_id)}>Update</button></td></tr>)}</tbody></table></div></section></AppShell>;
}
