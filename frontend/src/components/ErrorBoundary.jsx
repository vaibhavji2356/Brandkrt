import React from "react";
import { Link } from "react-router-dom";
import { AlertTriangle } from "lucide-react";

export default class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error("App crashed:", error, info); }
  reset = () => this.setState({ error: null });
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center px-6" data-testid="error-boundary">
        <div className="max-w-md text-center">
          <AlertTriangle className="h-12 w-12 mx-auto text-destructive" />
          <h1 className="mt-6 text-3xl font-display font-light tracking-tight text-primary dark:text-white">Something broke.</h1>
          <p className="mt-3 text-sm text-muted-foreground">An unexpected error occurred. Our engineers have been notified.</p>
          <div className="mt-8 flex gap-3 justify-center">
            <button onClick={this.reset} data-testid="error-reset" className="rounded-full bg-primary text-primary-foreground px-5 py-2.5 text-sm font-semibold">Try again</button>
            <Link to="/" className="rounded-full border border-border px-5 py-2.5 text-sm font-semibold">Back home</Link>
          </div>
        </div>
      </div>
    );
  }
}
