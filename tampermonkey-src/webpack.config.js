const path = require('path');
const TerserPlugin = require('terser-webpack-plugin');

// Userscript header - preserved at top of bundle
const userscriptHeader = `// ==UserScript==
// @name         Elite Pocket Option Trading Bot
// @namespace    https://momentum-trade-test.preview.emergentagent.com
// @version      8.17.1
// @description  Elite AI-powered trading bot - WS tick capture, 21s Reversal via direct-WS, SSID Bridge, IQ-720 Ensemble, Keltner-MACD 5s, smart inversion, CYCLE mode
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
