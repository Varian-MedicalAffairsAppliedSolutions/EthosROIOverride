const { app, BrowserWindow, Menu, shell } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    },
    // Show menu on Alt (Windows) while keeping the UI clean by default
    autoHideMenuBar: true
  });
  const pkg = require('./package.json');
  const version = app.getVersion();
  const build = String(pkg.buildNumber || 1);
  // Start at the licensing gate; it will redirect to main UI after registration
  win.loadFile('gate/index.html', { query: { version, build } });

  // Build and set application menu with Help -> About
  const template = [
    {
      label: 'File',
      submenu: [
        { role: 'close' }
      ]
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forcereload' },
        { type: 'separator' },
        { role: 'toggledevtools' },
        { type: 'separator' },
        { role: 'resetzoom' },
        { role: 'zoomin' },
        { role: 'zoomout' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    {
      role: 'help',
      submenu: [
        {
          label: `About ROI Override Tool v${app.getVersion()}`,
          accelerator: 'F1',
          click: () => openAboutWindow()
        },
        { type: 'separator' },
        {
          label: 'View Changelog',
          click: () => shell.openPath(path.join(__dirname, 'CHANGELOG.md'))
        },
        {
          label: 'Open README',
          click: () => shell.openPath(path.join(__dirname, 'README.md'))
        }
      ]
    }
  ];
  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

function openAboutWindow() {
  const about = new BrowserWindow({
    width: 820,
    height: 900,
    resizable: true,
    minimizable: false,
    maximizable: true,
    title: 'About',
    modal: false,
    webPreferences: {
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false
    }
  });
  const version = app.getVersion();
  const pkg = require('./package.json');
  const build = String(pkg.buildNumber || 1);
  about.setMenuBarVisibility(false);
  about.loadFile('about.html', { query: { version, build } });
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
