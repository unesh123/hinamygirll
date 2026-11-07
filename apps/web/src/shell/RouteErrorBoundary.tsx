import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "../design-system/hud";

interface Props { children: ReactNode; resetKey: string }
interface State { error: Error | null }

/** Keeps a crashing page from taking the whole shell (and the palette) down. */
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Route crashed", error, info.componentStack);
  }

  componentDidUpdate(prev: Props): void {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null });
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children;
    return (
      <div className="shell-state" data-kind="error" role="alert">
        <span>This page hit an error: {this.state.error.message}</span>
        <Button variant="secondary" onClick={() => this.setState({ error: null })}>Try again</Button>
      </div>
    );
  }
}
