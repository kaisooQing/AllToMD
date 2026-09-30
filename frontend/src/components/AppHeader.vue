<template>
  <header class="app-header">
    <div class="header-inner">
      <div class="brand">
        <img src="/favicon-512.png" class="brand-logo" alt="logo" />
        <h1 class="brand-name">{{ $t('app.title') }}</h1>
        <span class="brand-sep"></span>
        <span class="brand-desc">{{ $t('app.subtitle') }}</span>
      </div>
      <div class="powered-wrap">
        <span class="powered">{{ $t('app.poweredBy') }}</span>
        <span class="author">{{ $t('app.author') }}</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  flex: none;
  height: 72px;
  background: linear-gradient(135deg, #0369a1 0%, #0284c7 40%, #0ea5e9 100%);
  display: flex;
  align-items: center;
  padding: 0 28px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(3, 105, 161, 0.25);
}

.app-header::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 600px 120% at 10% 50%, rgba(255,255,255,0.10) 0%, transparent 60%),
    radial-gradient(ellipse 400px 100% at 90% 60%, rgba(255,255,255,0.06) 0%, transparent 50%);
  pointer-events: none;
}

.header-inner {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  z-index: 1;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-logo {
  width: 48px;
  height: 48px;
  flex-shrink: 0;
  border-radius: 10px;
  object-fit: cover;
  filter: drop-shadow(0 2px 6px rgba(0,0,0,0.2));
}

.brand-name {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.5px;
  color: #fff;
  text-shadow: 0 1px 4px rgba(0,0,0,0.12);
}

.brand-sep {
  width: 1px;
  height: 20px;
  background: rgba(255, 255, 255, 0.3);
  border-radius: 1px;
}

.brand-desc {
  font-size: 13px;
  font-weight: 400;
  color: rgba(255, 255, 255, 0.82);
  letter-spacing: 0.2px;
}

.powered-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.powered {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 500;
}

.author {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.55);
  letter-spacing: 0.3px;
  font-weight: 400;
}
</style>
