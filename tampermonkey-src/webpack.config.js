const path = require('path');
const fs = require('fs');
const webpack = require('webpack');
const TerserPlugin = require('terser-webpack-plugin');

// Single source of truth for the userscript version.
// IMPORTANT: This @version is what Tampermonkey checks to decide whether to
// re-install the script. If this number doesn't increase, TM keeps serving
// the old cached version and ALL bundle changes are invisible to the user.
// Bump /app/tampermonkey-src/version.txt for every release.
const SCRIPT_VERSION = fs
  .readFileSync(path.resolve(__dirname, 'version.txt'), 'utf8')
  .trim();

// Userscript header - preserved at top of bundle
const userscriptHeader = `// ==UserScript==
// @name         AI's Elite PO Traders Bot
// @namespace    https://pocket-option-ai-9.preview.emergentagent.com
// @version      ${SCRIPT_VERSION}
// @description  AI's Elite PO Traders Bot - CYCLE mode, APP signal poller, A-INV toggle, 21s + 51s Reversal via direct-WS, SSID Bridge, persistent settings
// @author       Elite Trading
// @match        *://*.pocketoption.com/*
// @match        *://pocketoption.com/*
// @match        *://*.po.trade/*
// @match        *://po.trade/*
// @match        *://*.pocket-option.com/*
// @match        *://pocket-option.com/*
// @match        *://*.po.market/*
// @match        *://po.market/*
// @grant        GM_addStyle
// @grant        GM_notification
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_log
// @connect      momentum-trade-test.preview.emergentagent.com
// @connect      preview.emergentagent.com
// @run-at       document-start
// @noframes
// ==/UserScript==
`;

module.exports = {
  entry: './src/index.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'pocket-option-auto-trader.user.js',
  },
  optimization: {
    minimize: true,
    minimizer: [
      new TerserPlugin({
        terserOptions: {
          format: {
            comments: false,
            preamble: userscriptHeader,
          },
        },
        extractComments: false,
      }),
    ],
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env'],
          },
        },
      },
    ],
  },
  plugins: [
    // Inject the version from version.txt so config.js BOT_VERSION matches
    // the @version in the userscript header. Single source of truth.
    new webpack.DefinePlugin({
      __SCRIPT_VERSION__: JSON.stringify(SCRIPT_VERSION),
    }),
  ],
  resolve: {
    extensions: ['.js'],
    alias: {
      '@core': path.resolve(__dirname, 'src/core'),
      '@strategies': path.resolve(__dirname, 'src/strategies'),
      '@ui': path.resolve(__dirname, 'src/ui'),
      '@trading': path.resolve(__dirname, 'src/trading'),
      '@utils': path.resolve(__dirname, 'src/utils'),
      '@data': path.resolve(__dirname, 'src/data'),
    },
  },
  mode: 'production',
  target: ['web', 'es2020'],
};
