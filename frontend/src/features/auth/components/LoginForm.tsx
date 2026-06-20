import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card } from "@/components/ui/Card";
import { useToastStore } from "@/stores/toastStore";

export function LoginForm() {
  const navigate = useNavigate();
  const { login, isLoggingIn } = useAuth();
  const addToast = useToastStore((s) => s.addToast);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      await login({ email, password });
      addToast({ level: "success", title: "Login successful" });
      navigate("/pipeline");
    } catch {
      addToast({ level: "error", title: "Login failed", message: "Invalid credentials." });
    }
  }

  return (
    <Card className="mx-auto max-w-md">
      <h2 className="mb-6 text-xl font-bold text-gray-900">Sign In</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          label="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Button type="submit" loading={isLoggingIn} className="w-full">
          Sign In
        </Button>
      </form>
    </Card>
  );
}
