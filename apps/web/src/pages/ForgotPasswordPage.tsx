import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles, Mail, AlertCircle, CheckCircle2 } from 'lucide-react';
import { authApi } from '../api/auth';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { getErrorMessage } from '../utils/error';

export const ForgotPasswordPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setError(null);
    setStatusMsg(null);
    setLoading(true);

    try {
      const res = await authApi.forgotPassword(email);
      setStatusMsg(res.message);
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
          Reset Your Password
        </h2>
        <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] font-medium">Enter your registered email address to receive a reset link</p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md z-10">
        <div className="bg-[#102C4D] border border-[#1D4E78] py-8 px-6 shadow-2xl rounded-2xl sm:px-10">
          <form className="space-y-5" onSubmit={handleSubmit}>
            {error && (
              <div className="flex items-center space-x-2 text-[13px] sm:text-[14px] text-[#EF4444] bg-[#EF4444]/15 p-3 rounded-lg border border-[#EF4444]/40 font-medium">
                <AlertCircle className="w-4 h-4 flex-shrink-0 text-[#EF4444]" />
                <span>{getErrorMessage(error)}</span>
              </div>
            )}

            {statusMsg && (
              <div className="flex items-center space-x-2 text-[13px] sm:text-[14px] text-[#10B981] bg-[#10B981]/15 p-3 rounded-lg border border-[#10B981]/40 font-medium">
                <CheckCircle2 className="w-4 h-4 flex-shrink-0 text-[#10B981]" />
                <span>{statusMsg}</span>
              </div>
            )}

            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              icon={<Mail />}
              required
            />

            <Button type="submit" className="w-full" isLoading={loading}>
              Send Reset Link
            </Button>
          </form>

          <div className="mt-6 text-center text-[13px] sm:text-[14px] text-[#8FA4BD]">
            Remember your password?{' '}
            <Link to="/login" className="font-semibold text-[#3B82F6] hover:text-blue-300 transition-colors">
              Back to Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
