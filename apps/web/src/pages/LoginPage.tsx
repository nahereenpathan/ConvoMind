import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sparkles, Mail, Lock, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { useAuthStore } from '../stores/useAuthStore';
import { Button } from '../components/ui/Button';
import { getErrorMessage } from '../utils/error';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [loading, setLoading] = useState(false);

  const { login } = useAuthStore();
  const navigate = useNavigate();

  const validate = (): boolean => {
    const errors: { email?: string; password?: string } = {};
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      errors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      errors.password = 'Password is required.';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (loading) return; // Prevent duplicate concurrent requests

    setError(null);

    if (!validate()) {
      return;
    }

    setLoading(true);

    try {
      const normalizedEmail = email.trim().toLowerCase();
      await login(normalizedEmail, password);
      navigate('/');
    } catch (err: any) {
      const serverMsg = getErrorMessage(err);
      if (serverMsg.toLowerCase().includes('network') || serverMsg.toLowerCase().includes('econnrefused')) {
        setError('Unable to connect to the server. Please try again.');
      } else {
        setError(serverMsg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#06152F] flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden text-[#F8FAFC]">
      {/* Subtle ambient lighting */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-[#2563EB]/15 rounded-full blur-[120px] pointer-events-none" />

      {/* Header / Branding */}
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center z-10 space-y-3">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-[#2563EB] text-white shadow-xl border border-[#3B82F6]/40">
          <Sparkles className="w-7 h-7" />
        </div>
        <h2 className="text-[28px] sm:text-[32px] font-extrabold tracking-tight text-[#F8FAFC]">
          Welcome back
        </h2>
        <p className="text-[14px] sm:text-[15px] text-[#B8C7DA] font-medium">
          Sign in to continue to your workspace
        </p>
      </div>

      {/* Main Login Card */}
      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md z-10">
        <div className="bg-[#102C4D] border border-[#1D4E78] py-8 px-6 shadow-2xl rounded-2xl sm:px-10 space-y-6">
          <form className="space-y-5" onSubmit={handleSubmit} noValidate>
            {/* Global Error Banner */}
            {error && (
              <div className="flex items-start space-x-2 text-[13px] sm:text-[14px] text-[#EF4444] bg-[#EF4444]/15 p-3.5 rounded-xl border border-[#EF4444]/30 font-medium">
                <AlertCircle className="w-5 h-5 flex-shrink-0 text-[#EF4444] mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Email Field */}
            <div className="space-y-1.5">
              <label htmlFor="login-email" className="block text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA]">
                Email address
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#8FA4BD]">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (fieldErrors.email) setFieldErrors((prev) => ({ ...prev, email: undefined }));
                  }}
                  placeholder="you@company.com"
                  className={`w-full bg-[#0A1B35] border ${
                    fieldErrors.email
                      ? 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]/20'
                      : 'border-[#1D4E78] focus:border-[#3B82F6] focus:ring-[#3B82F6]/20'
                  } text-[#F8FAFC] placeholder-[#8FA4BD] text-[14px] sm:text-[15px] rounded-xl pl-10 pr-3.5 py-2.5 shadow-sm transition-all duration-150 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed`}
                  disabled={loading}
                  autoComplete="email"
                  required
                />
              </div>
              {fieldErrors.email && (
                <p className="text-[12px] sm:text-[13px] text-[#EF4444] font-medium pt-0.5">{fieldErrors.email}</p>
              )}
            </div>

            {/* Password Field */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label htmlFor="login-password" className="block text-[13px] sm:text-[14px] font-semibold text-[#B8C7DA]">
                  Password
                </label>
                <Link
                  to="/forgot-password"
                  className="text-[13px] text-[#3B82F6] hover:text-blue-300 font-medium transition-colors"
                >
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#8FA4BD]">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (fieldErrors.password) setFieldErrors((prev) => ({ ...prev, password: undefined }));
                  }}
                  placeholder="••••••••"
                  className={`w-full bg-[#0A1B35] border ${
                    fieldErrors.password
                      ? 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]/20'
                      : 'border-[#1D4E78] focus:border-[#3B82F6] focus:ring-[#3B82F6]/20'
                  } text-[#F8FAFC] placeholder-[#8FA4BD] text-[14px] sm:text-[15px] rounded-xl pl-10 pr-10 py-2.5 shadow-sm transition-all duration-150 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed`}
                  disabled={loading}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[#8FA4BD] hover:text-[#F8FAFC] transition-colors focus:outline-none"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {fieldErrors.password && (
                <p className="text-[12px] sm:text-[13px] text-[#EF4444] font-medium pt-0.5">{fieldErrors.password}</p>
              )}
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              className="w-full py-2.5 rounded-xl text-[15px] font-bold shadow-lg mt-2"
              isLoading={loading}
              disabled={loading}
            >
              {loading ? 'Signing In...' : 'Sign In to Account'}
            </Button>
          </form>

          {/* Create Account Link */}
          <div className="pt-2 text-center text-[13px] sm:text-[14px] text-[#8FA4BD]">
            Don't have an account?{' '}
            <Link to="/register" className="font-semibold text-[#3B82F6] hover:text-blue-300 transition-colors">
              Create Account
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
