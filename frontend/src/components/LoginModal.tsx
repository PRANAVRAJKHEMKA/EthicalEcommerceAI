import { useState, useEffect } from 'react';
import { X, Lock, User, Eye, EyeOff, ShieldCheck, AlertCircle, Sparkles, Loader2, ArrowRight } from 'lucide-react';
import { UserProfile, DemoPersona } from '../types.ts';
import { loginUser, demoLoginUser, fetchDemoPersonas } from '../api.ts';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLoginSuccess: (user: UserProfile) => void;
}

export function LoginModal({ isOpen, onClose, onLoginSuccess }: LoginModalProps) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [personas, setPersonas] = useState<DemoPersona[]>([]);
  const [selectedPersona, setSelectedPersona] = useState<DemoPersona | null>(null);

  useEffect(() => {
    if (isOpen) {
      setErrorMessage(null);
      fetchDemoPersonas()
        .then((data) => {
          setPersonas(data);
          if (data.length > 0 && !username) {
            const first = data[0];
            setSelectedPersona(first);
            setUsername(first.username);
          }
        })
        .catch(() => {
          // If demo-personas endpoint fails, fallback to standard demo accounts metadata
          setPersonas([
            { id: '1', username: 'demo_gamer', display_name: 'Alex Mercer', tag: 'Gamer', persona_description: 'Competitive gaming and esports peripherals enthusiast' },
            { id: '2', username: 'demo_student', display_name: 'Maya Lin', tag: 'Student', persona_description: 'Compact study nook and eye comfort researcher' },
            { id: '3', username: 'demo_creator', display_name: 'Devon Reed', tag: 'Creator', persona_description: '4K video streaming and studio acoustics producer' },
            { id: '4', username: 'demo_traveler', display_name: 'Jordan Hayes', tag: 'Traveler', persona_description: 'Digital nomad valuing compact GaN power and travel gear' },
            { id: '5', username: 'demo_office', display_name: 'Sarah Jenkins', tag: 'Office Pro', persona_description: 'Ergonomic dual-monitor and posture health specialist' },
          ]);
        });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSelectPersona = (p: DemoPersona) => {
    setSelectedPersona(p);
    setUsername(p.username);
    setErrorMessage(null);
  };

  const handleDemoSignIn = async (personaUsername: string) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await demoLoginUser(personaUsername);
      onLoginSuccess(response.user);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Demo authentication failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setErrorMessage('Please enter both username and password.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const response = await loginUser({ username: username.trim(), password });
      onLoginSuccess(response.user);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="flex min-h-screen items-center justify-center p-4">
        <div
          className="relative w-full max-w-lg rounded-2xl bg-white p-6 md:p-8 shadow-2xl transition-all border border-slate-100"
          role="dialog"
          aria-modal="true"
        >
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute right-4 top-4 rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Header */}
          <div className="flex items-center gap-3 mb-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">Sign In to FairCart AI</h2>
              <p className="text-xs text-slate-500">Evaluation Demonstration Authentication</p>
            </div>
          </div>

          {/* Demo Persona Chips */}
          <div className="my-4 p-3.5 rounded-xl bg-slate-50 border border-slate-200">
            <div className="flex items-center gap-1.5 mb-2.5">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              <span className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Select Demo Persona to Pre-Fill
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {personas.map((p) => {
                const isSelected = selectedPersona?.username === p.username || username === p.username;
                return (
                  <button
                    key={p.username}
                    type="button"
                    onClick={() => handleSelectPersona(p)}
                    className={`text-xs px-2.5 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
                      isSelected
                        ? 'bg-indigo-600 text-white shadow-sm ring-2 ring-indigo-300'
                        : 'bg-white text-slate-700 border border-slate-200 hover:bg-slate-100'
                    }`}
                  >
                    <span>{p.display_name}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.2 rounded font-normal ${
                        isSelected ? 'bg-indigo-700 text-indigo-100' : 'bg-slate-100 text-slate-500'
                      }`}
                    >
                      {p.tag}
                    </span>
                  </button>
                );
              })}
            </div>

            {selectedPersona && (
              <div className="mt-3 pt-2.5 border-t border-slate-200 flex flex-col gap-2">
                <p className="text-[11px] text-slate-600 italic">
                  &ldquo;{selectedPersona.persona_description}&rdquo;
                </p>
                <button
                  type="button"
                  disabled={isLoading}
                  onClick={() => handleDemoSignIn(selectedPersona.username)}
                  className="w-full flex items-center justify-center gap-2 py-2 px-3 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition-all text-xs disabled:opacity-60 cursor-pointer"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Authenticating demo persona...</span>
                    </>
                  ) : (
                    <>
                      <span>Quick Demo Sign-In as {selectedPersona.display_name}</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          <div className="relative my-4">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-[10px] uppercase">
              <span className="bg-white px-2 text-slate-400 font-medium">Or Sign In with Password</span>
            </div>
          </div>

          {/* Error Message */}
          {errorMessage && (
            <div className="mb-4 flex items-center gap-2 rounded-lg bg-rose-50 p-3 text-xs text-rose-700 border border-rose-200">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-500" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Username</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <User className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => {
                    setUsername(e.target.value);
                    setSelectedPersona(null);
                  }}
                  className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent font-mono"
                  placeholder="demo_gamer"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-9 pr-10 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent font-mono"
                  placeholder="Enter account password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg shadow-sm transition-colors text-sm disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Verifying Argon2id credentials...</span>
                </>
              ) : (
                <span>Sign In {selectedPersona ? `as ${selectedPersona.display_name}` : ''}</span>
              )}
            </button>
          </form>

          {/* Security & Isolation Callout */}
          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
            <span>Argon2id Hashing</span>
            <span>•</span>
            <span>Zero Merchant Privileges</span>
            <span>•</span>
            <span>Isolated Order History</span>
          </div>
        </div>
      </div>
    </div>
  );
}
