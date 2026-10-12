import { useState } from 'react';
import type { AiLogin, AiModel, AiProvider, AiProviderId, AiSelection, AiState } from './api';

const descriptions: Record<AiProviderId, string> = {
  codex: 'Dùng tài khoản ChatGPT của bạn qua Codex CLI.',
  antigravity: 'Dùng phiên Google trong Antigravity CLI.',
  claude: 'Dùng tài khoản Claude của bạn qua Claude Code.',
};

function EffortPicker({ model, value, disabled, label, onChange }: {
  model?: AiModel; value: string; disabled: boolean; label: string; onChange: (value: string) => void;
}) {
  if (!model?.efforts?.length) return null;
  return <label className="provider-model">Effort<select aria-label={label} value={value} disabled={disabled} onChange={event => onChange(event.target.value)}>
    <option value="">Mặc định{model.default_effort ? ` (${model.default_effort})` : ' của provider'}</option>
    {model.efforts.map(effort => <option key={effort.id} value={effort.id} title={effort.description}>{effort.name}</option>)}
  </select></label>;
}

export function AiPicker({ state, busy, onSelect, onConnect }: {
  state: AiState | null; busy: boolean; onSelect: (selection: AiSelection) => Promise<void>; onConnect: () => void;
}) {
  const selectedProvider = state?.providers.find(p => p.id === state.selection?.provider);
  const selectedModel = selectedProvider?.models.find(m => m.id === state?.selection?.model);
  return <div className="ai-picker">
    <label>Provider<select aria-label="Provider AI" value={state?.selection?.provider || ''} disabled={busy || !state} onChange={event => {
      const provider = state?.providers.find(p => p.id === event.target.value);
      const model = provider?.models.find(m => m.default) || provider?.models[0];
      if (provider && model) void onSelect({ provider: provider.id, model: model.id, effort: model.default_effort || undefined });
    }}><option value="" disabled>Chọn tài khoản AI</option>{state?.providers.map(p => <option key={p.id} value={p.id} disabled={!p.connected || !p.models.length}>{p.name}{p.connected ? '' : ' · Chưa kết nối'}</option>)}</select></label>
    <label>Model<select aria-label="Model AI" value={state?.selection?.model || ''} disabled={busy || !selectedProvider?.connected} onChange={event => {
      if (selectedProvider) {
        const model = selectedProvider.models.find(m => m.id === event.target.value);
        void onSelect({ provider: selectedProvider.id, model: event.target.value, effort: model?.default_effort || undefined });
      }
    }}><option value="" disabled>Chọn model</option>{selectedProvider?.models.map(model => <option key={model.id} value={model.id}>{model.name}</option>)}</select></label>
    <EffortPicker model={selectedModel} value={state?.selection?.effort || ''} disabled={busy || !selectedProvider?.connected} label="Effort AI" onChange={effort => {
      if (selectedProvider && selectedModel) void onSelect({ provider: selectedProvider.id, model: selectedModel.id, effort: effort || undefined });
    }} />
    <button className="text-button" type="button" onClick={onConnect}>Kết nối tài khoản</button>
  </div>;
}

function ProviderCard({ provider, selected, ownsSession, busy, onSelect, onLogin, onLogout, onCancel }: {
  provider: AiProvider; selected: AiSelection | null; ownsSession: boolean; busy: boolean;
  onSelect: (selection: AiSelection) => Promise<void>; onLogin: (provider: AiProviderId, device?: boolean) => void;
  onLogout: (provider: AiProviderId) => void;
  onCancel: (provider: AiProviderId) => void;
}) {
  const [draftModel, setDraftModel] = useState('');
  const [draftEffort, setDraftEffort] = useState<{ model: string; effort: string } | null>(null);
  const model = provider.models.find(m => m.id === draftModel)?.id ||
    (selected?.provider === provider.id && provider.models.some(m => m.id === selected.model) ? selected.model : '') ||
    provider.models.find(m => m.default)?.id || provider.models[0]?.id || '';
  const selectedModel = provider.models.find(m => m.id === model);
  const efforts = selectedModel?.efforts || [];
  const savedEffort = selected?.provider === provider.id && selected.model === model ? selected.effort || '' : '';
  const effort = draftEffort?.model === model && (!draftEffort.effort || efforts.some(e => e.id === draftEffort.effort)) ? draftEffort.effort
    : efforts.some(e => e.id === savedEffort) ? savedEffort : selectedModel?.default_effort || '';
  const effectiveEffort = effort || selectedModel?.default_effort || undefined;
  const active = selected?.provider === provider.id && selected.model === model && (selected.effort || undefined) === effectiveEffort;
  const loginDisabled = busy || !provider.installed || provider.blocked || provider.pending;
  return <article className={`panel provider-card ${ownsSession ? 'provider-active' : ''}`}>
    <div className="provider-heading"><div><span className="eyebrow">{provider.id === 'codex' ? 'CHATGPT' : provider.id.toUpperCase()}</span><h2>{provider.name}</h2></div><span className={`provider-status ${provider.connected ? 'provider-connected' : ''}`}><span className="status-led" />{provider.connected ? 'Đã kết nối' : provider.pending ? 'Đang đăng nhập' : provider.installed ? ownsSession ? 'Cần kết nối lại' : 'Chưa kết nối' : 'Chưa cài CLI'}</span></div>
    <p>{descriptions[provider.id]}</p>
    {provider.connected ? <>
      <div className="provider-account"><span>{provider.account || 'Phiên CLI trên máy này'}</span>{provider.plan && <small>{provider.plan}</small>}</div>
      <label className="provider-model">Model khả dụng<select aria-label={`Model ${provider.name}`} value={model} disabled={busy} onChange={event => setDraftModel(event.target.value)}>{provider.models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
      <EffortPicker model={selectedModel} value={effort} disabled={busy} label={`Effort ${provider.name}`} onChange={effort => setDraftEffort({ model, effort })} />
      <div className="provider-actions"><button className={`button ${active ? 'button-secondary' : 'button-primary'}`} disabled={busy || active || !model} onClick={() => void onSelect({ provider: provider.id, model, effort: effort || undefined })}>{active ? 'Đang sử dụng' : 'Áp dụng'}</button><button className="text-button" disabled={busy} onClick={() => onLogout(provider.id)}>Đăng xuất</button></div>
    </> : <>
      <p className="provider-detail">{provider.message || 'Đăng nhập để tải danh sách model của tài khoản.'}</p>
      <div className="provider-actions"><button className="button button-primary" disabled={loginDisabled} onClick={() => onLogin(provider.id)}>{provider.pending ? 'Đang đăng nhập...' : ownsSession ? 'Kết nối lại' : provider.id === 'codex' ? 'Đăng nhập ChatGPT' : 'Mở đăng nhập CLI'}</button>{ownsSession && <button className="text-button" disabled={busy} onClick={() => onLogout(provider.id)}>Đăng xuất</button>}{provider.pending && <button className="text-button" disabled={busy} onClick={() => onCancel(provider.id)}>Hủy đăng nhập</button>}{provider.id === 'codex' && provider.installed && !ownsSession && <button className="text-button" disabled={loginDisabled} onClick={() => onLogin(provider.id, true)}>Dùng mã thiết bị</button>}</div>
    </>}
  </article>;
}

export default function AiConnections({ state, busy, login, onRefresh, onSelect, onLogin, onCancel, onLogout }: {
  state: AiState | null; busy: boolean; login: AiLogin | null; onRefresh: () => void;
  onSelect: (selection: AiSelection) => Promise<void>; onLogin: (provider: AiProviderId, device?: boolean) => void;
  onCancel: (provider?: AiProviderId) => void; onLogout: (provider: AiProviderId) => void;
}) {
  return <>
    <div className="page-header"><div><div className="eyebrow">LOCAL CLI <span className="eyebrow-separator">/</span> AI CONNECTIONS</div><h1>Kết nối AI</h1><p>Kết nối một tài khoản AI để dùng cho các kỹ năng TestAgent.</p></div><button className="button button-secondary" disabled={busy} onClick={onRefresh}>{busy ? 'Đang xử lý...' : 'Kiểm tra kết nối'}</button></div>
    <div className="ai-explanation"><strong>Mỗi lần chỉ kết nối một provider</strong><p>Model mặc định được chọn ngay khi kết nối. Bạn có thể đổi model và effort nếu được hỗ trợ; để chuyển provider, hãy đăng xuất tài khoản hiện tại. Hạn mức theo tài khoản, không cần nhập API key.</p></div>
    {login && <section className="panel login-panel" role="status"><h2>Hoàn tất đăng nhập {state?.providers.find(p => p.id === login.provider)?.name}</h2><p>{login.message}</p>{login.user_code && <div className="device-code"><span>Mã thiết bị</span><code>{login.user_code}</code></div>}<div className="provider-actions">{login.url && <a className="button button-primary" href={login.url} target="_blank" rel="noreferrer">Mở trang đăng nhập</a>}<button className="button button-secondary" disabled={busy} onClick={onRefresh}>Tôi đã đăng nhập</button><button className="text-button" disabled={busy} onClick={() => onCancel()}>Hủy đăng nhập</button></div></section>}
    {state ? <div className="provider-grid">{state.providers.map(provider => <ProviderCard key={provider.id} provider={provider} selected={state.selection} ownsSession={state.active_provider === provider.id} busy={busy} onSelect={onSelect} onLogin={onLogin} onLogout={onLogout} onCancel={onCancel} />)}</div> : <div className="panel provider-loading" role="status">Đang kiểm tra các CLI và phiên đăng nhập...</div>}
    <p className="ai-footnote">Đăng xuất ngắt kết nối tài khoản khỏi TestAgent và được lưu qua lần khởi động lại. Tài khoản trong CLI trên máy vẫn do provider quản lý.</p>
  </>;
}
