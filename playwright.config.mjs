import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./uat/browser',timeout:60000,expect:{timeout:15000},workers:1,retries:0,
  reporter:[['list']],outputDir:'test-results',
  use:{baseURL:'http://127.0.0.1:38189',browserName:'chromium',
    launchOptions:process.env.TAMASYA_UAT_CHROME?{executablePath:process.env.TAMASYA_UAT_CHROME}:{},
    trace:'off',video:'off',screenshot:'off',serviceWorkers:'block'},
  projects:[{name:'desktop',use:{viewport:{width:1440,height:1000}}},
    {name:'mobile',use:{viewport:{width:390,height:844},isMobile:true,hasTouch:true}}]
});
