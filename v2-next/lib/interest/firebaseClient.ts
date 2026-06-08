/* ------------------------------------------------------------------
   Firebase client — modular SDK 初期化 (client-side only)

   - Firebase JS SDK の modular API を使用。
   - 静的エクスポート (output: 'export') 環境のため、初期化は必ず
     ブラウザ実行時に遅延的に行う (SSR / ビルド時には触らない)。
   - 使用するのは Authentication (Google) と Firestore のみ。
   ------------------------------------------------------------------ */
'use client';

import { initializeApp, getApps, getApp, type FirebaseApp } from 'firebase/app';
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  type Auth,
  type User,
} from 'firebase/auth';
import { getFirestore, type Firestore } from 'firebase/firestore';
import { ALLOWED_EMAIL, firebaseConfig } from './config';

interface FirebaseHandles {
  app: FirebaseApp;
  auth: Auth;
  db: Firestore;
}

let _handles: FirebaseHandles | null = null;

/** ブラウザでのみ Firebase を初期化して handle を返す。SSR では null。 */
export function getFirebase(): FirebaseHandles | null {
  if (typeof window === 'undefined') return null;
  if (_handles) return _handles;
  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  const auth = getAuth(app);
  const db = getFirestore(app);
  _handles = { app, auth, db };
  return _handles;
}

/** 許可メール (= 本人) かどうか。Rules 側でも同じ判定を強制している。 */
export function isAllowedUser(user: User | null | undefined): boolean {
  return !!user && user.email === ALLOWED_EMAIL;
}

/** Google ログイン。許可メール以外でログインされても呼び出し側で弾く。 */
export async function signInWithGoogle(): Promise<User | null> {
  const fb = getFirebase();
  if (!fb) return null;
  const provider = new GoogleAuthProvider();
  // 毎回アカウント選択を出して、誤アカウントでの記録を避ける
  provider.setCustomParameters({ prompt: 'select_account' });
  const cred = await signInWithPopup(fb.auth, provider);
  return cred.user;
}

export async function signOutUser(): Promise<void> {
  const fb = getFirebase();
  if (!fb) return;
  await signOut(fb.auth);
}

/** auth 状態を監視。返り値で unsubscribe。 */
export function watchAuth(cb: (user: User | null) => void): () => void {
  const fb = getFirebase();
  if (!fb) return () => {};
  return onAuthStateChanged(fb.auth, cb);
}

export type { User };
