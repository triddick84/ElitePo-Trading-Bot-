const path = require('path');
const TerserPlugin = require('terser-webpack-plugin');

// Userscript header - preserved at top of bundle
const userscriptHeader = `// ==UserScript==
// @name         GPT Signal Bot - Pocket Option Auto Trader
// @namespace    https://pocket-trader-ai-8.preview.emergentagent.com
// @version      7.7.0
// @description  Auto-trade OTC forex on Pocket Option. Modular build with advanced AI/ML strategies.
// @author       GPT Signal Bot
// @match        *://*.pocketoption.com/*
// @match        *://pocketoption.com/*
// @match        *://*.po.trade/*
// @match        *://po.trade/*
// @match        *://*.pocket-option.com/*
// @match        *://pocket-option.com/*
// @match        *://*.po.market/*
// @match        *://po.market/*
// @grant        GM_notification
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_log
// @connect      signal-bot-staging.preview.emergentagent.com
// @connect      pocket-option-auto-2.preview.emergentagent.com
// @connect      ai-broker-dev.preview.emergentagent.com
// @connect      *.preview.emergentagent.com
// @connect      *
// @run-at       document-idle
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
