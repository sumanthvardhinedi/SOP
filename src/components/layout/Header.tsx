import { LogOut, Store } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import { Brand } from "./Brand";

export function Header() {
  const { user, signOut } = useAuth();
  if (!user) return null;
  return (
    <header className="app-header">
      <div className="header-inner">
        <Brand />
        <div className="header-account">
          <span className="shop-badge">
            <Store size={14} aria-hidden="true" />
            Shop {user.shop_id}
          </span>
          <div className="account-details">
            <strong>{user.name}</strong>
            <span>{user.email}</span>
          </div>
          <button
            className="icon-button logout"
            onClick={signOut}
            aria-label="Log out"
            title="Log out"
          >
            <LogOut size={18} />
            <span>Log out</span>
          </button>
        </div>
      </div>
    </header>
  );
}
