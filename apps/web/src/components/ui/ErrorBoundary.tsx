import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { getErrorMessage } from '../../utils/error';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: any;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in UI component:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center text-slate-900">
          <div className="max-w-md w-full bg-white border border-slate-200 p-8 rounded-2xl space-y-4 shadow-xl">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-rose-50 text-rose-600 border border-rose-200">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">Something went wrong</h2>
            <p className="text-xs text-slate-500 leading-relaxed">
              An unexpected user interface error occurred. Please try reloading the page.
            </p>
            {this.state.error && (
              <pre className="text-[11px] font-mono text-rose-700 bg-rose-50 p-3 rounded-lg border border-rose-200 text-left overflow-x-auto max-h-32">
                {getErrorMessage(this.state.error)}
              </pre>
            )}
            <button
              onClick={this.handleReset}
              className="w-full inline-flex items-center justify-center space-x-2 py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs shadow-md transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Reload Application</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
