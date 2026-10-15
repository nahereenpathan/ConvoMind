import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sparkles, Mail, Lock, User, AlertCircle } from 'lucide-react';
import { useAuthStore } from '../stores/useAuthStore';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { getErrorMessage } from '../utils/error';

export const RegisterPage: React.FC = () => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { register } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password || !fullName) return;
    setError(null);
    setLoading(true);

    try {
      await register(email, password, fullName);
      navigate('/');
    } catch (err: any) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#06152F] flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden text-[#F8FAFC]">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-96 h-96 bg-[#2563EB]/20 rounded-full blur-3xl pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center z-10 space-y-3">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-[#2563EB] text-white shadow-lg border border-[#3B82F6]/50">
          <Sparkles className="w-6 h-6" />
        </div>
        <h2 className="text-[26px] sm:text-[30px] font-bold text-[#F8FAFC]">
          Create ConvoMind Account
        </h2>
        <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] font-medium">Join thousands of teams automating meeting workflows</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md z-10">
        <div className="bg-[#102C4D] border border-[#1D4E78] py-8 px-6 shadow-2xl rounded-2xl sm:px-10">
          <form className="space-y-5" onSubmit={handleSubmit}>
            {error && (
              <div className="space-y-2 text-[13px] sm:text-[14px] text-[#EF4444] bg-[#EF4444]/15 p-3 rounded-lg border border-[#EF4444]/40 font-medium">
                <div className="flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 text-[#EF4444]" />
                  <span>{error}</span>
                </div>
                {(error.toLowerCase().includes('already registered') || error.toLowerCase().includes('already exists')) && (
                  <div className="pt-1 border-t border-[#EF4444]/20 text-[#B8C7DA]">
                    Have an account already?{' '}
                    <Link to="/login" className="text-[#3B82F6] hover:underline font-semibold">
                      Sign in to your account →
                    </Link>
                  </div>
                )}
              </div>
            )}

            <Input
              label="Full Name"
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alice Smith"
              icon={<User />}
              required
            />

            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              icon={<Mail />}
              required
            />

            <div>
              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                icon={<Lock />}
                required
              />
              <p className="text-[12px] text-[#8FA4BD] mt-1.5 font-normal">
                Must be at least 8 characters with 1 uppercase, 1 lowercase, 1 number & 1 special character.
              </p>
            </div>

            <Button type="submit" className="w-full" isLoading={loading}>
              Create Account & Workspace
            </Button>
          </form>

          <div className="mt-6 text-center text-[13px] sm:text-[14px] text-[#8FA4BD]">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-[#3B82F6] hover:text-blue-300 transition-colors">
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
