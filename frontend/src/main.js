// frontend/src/main.js
import * as serverActions from './server_actions.js';

import { initializeDashboard } from './dashboard.js';
import { initializeAccountPage } from './account.js';
import { initializeAllowlistPage } from './allowlist.js';
import { initializeLoginPage } from './auth.js';
import * as backupRestore from './backup_restore.js';
import * as contentManagement from './content_management.js';
import * as installConfig from './install_config.js';
import { initializeManagePluginsPage } from './manage_plugins.js';
import { initializeManageSettingsPage } from './manage_settings.js';
import { initializeServerSettingsPage } from './server_settings.js';
import { initializeMonitorUsagePage } from './monitor_usage.js';
import { initializeSidebarNav } from './sidebar_nav.js';
import { handleQueryParameters } from './query_param_handler.js';
import { initializeUsersPage } from './users.js';
import { initializeRegisterPage } from './register.js';
import { initializeSetupPage } from './setup.js';
import webSocketClient from './websocket_client.js';

document.addEventListener('DOMContentLoaded', () => {
  // Establish WebSocket connection for the entire app
  webSocketClient.connect();

  // General initializations
  initializeSidebarNav();
  handleQueryParameters();

  // Page-specific initializations
  if (document.getElementById('server-card-list')) {
    initializeDashboard();
  } else if (document.getElementById('change-password-form')) {
    initializeAccountPage();
  } else if (document.getElementById('current-allowlist-display')) {
    initializeAllowlistPage();
  } else if (document.getElementById('login-form')) {
    initializeLoginPage();
  } else if (document.getElementById('backup-restore-page')) {
    backupRestore.initializeBackupRestorePage();
  } else if (document.getElementById('content-management-page')) {
    contentManagement.initializeContentManagementPage();
  } else if (document.getElementById('install-config-page')) {
    installConfig.initializeInstallConfigPage();
  } else if (document.getElementById('plugin-list')) {
    initializeManagePluginsPage();
  } else if (document.getElementById('settings-form-container')) {
    if (window.location.pathname.startsWith('/servers/')) {
      initializeServerSettingsPage();
    } else {
      initializeManageSettingsPage();
    }
  } else if (document.getElementById('status-info')) {
    initializeMonitorUsagePage();
  } else if (document.getElementById('user-management-section')) {
    initializeUsersPage();
  } else if (document.getElementById('register-form')) {
    initializeRegisterPage();
  } else if (document.getElementById('setup-form')) {
    initializeSetupPage();
  }

  console.log('main.js loaded and initialized');
});
