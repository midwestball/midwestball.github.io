import React from 'react';
import { Link, Outlet } from 'react-router-dom';

export default function MainLayout() {
    return (
        <div className="app-wrapper">
            <nav className="navbar">
                <div className="container nav-content">
                    <Link to="/" className="logo">
                        Knowball
                    </Link>
                    <div className="nav-links">
                        <Link to="/" className="nav-link">Home</Link>
                    </div>
                </div>
            </nav>

            <main className="main-content">
                <Outlet />
            </main>

            <style>{`
        .navbar {
          background: var(--color-surface);
          border-bottom: 1px solid var(--color-border);
          padding: var(--spacing-md) 0;
          position: sticky;
          top: 0;
          z-index: 10;
        }
        .nav-content {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .logo {
          font-size: 1.5rem;
          font-weight: 800;
          color: var(--color-primary);
          letter-spacing: -0.5px;
        }
        .nav-links {
          display: flex;
          gap: var(--spacing-md);
        }
        .nav-link {
          color: var(--color-text-secondary);
          font-weight: 500;
          transition: color 0.2s;
        }
        .nav-link:hover {
          color: var(--color-primary);
        }
        .main-content {
          min-height: calc(100vh - 64px);
          padding: var(--spacing-lg) 0;
        }
      `}</style>
        </div>
    );
}
