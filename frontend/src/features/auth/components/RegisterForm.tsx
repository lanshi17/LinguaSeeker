"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../hooks/useAuth";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { useToastStore } from "@/stores/toastStore";

export function RegisterForm() {
  const router = useRouter();
  const { register, isRegistering } = useAuth();
  const addToast = useToastStore((s) => s.addToast);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      addToast({ level: "error", title: "Passwords do not match" });
      return;
    }
    try {
      await register({ email, password, password_confirm: confirm });
      addToast({ level: "success", title: "Registration successful" });
      router.push("/login");
    } catch {
      addToast({ level: "error", title: "Registration failed" });
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <h2 className="mb-6 text-xl font-bold text-gray-900">Register</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <Input label="Confirm Password" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
        <Button type="submit" loading={isRegistering} className="w-full">Register</Button>
      </form>
    </Card>
  );
}
