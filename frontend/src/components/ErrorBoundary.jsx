import { Component } from "react";

export default class ErrorBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="page">
          <div className="card">
            <h2>Wystąpił błąd interfejsu</h2>
            <p className="muted">{String(this.state.error.message || this.state.error)}</p>
            <button className="btn" onClick={() => window.location.reload()}>Odśwież</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
