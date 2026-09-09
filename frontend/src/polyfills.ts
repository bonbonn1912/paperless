/**
 * Polyfills for modern ECMAScript features required by pdfjs-dist
 * when running under Angular Zone.js (ZoneAwarePromise) or in browsers
 * without native Promise.try and Promise.withResolvers.
 */

if (typeof (Promise as any).try !== 'function') {
  (Promise as any).try = function <T>(fn: (...args: any[]) => T, ...args: any[]): Promise<T> {
    return new Promise<T>((resolve) => {
      resolve(fn(...args));
    });
  };
}

if (typeof (Promise as any).withResolvers !== 'function') {
  (Promise as any).withResolvers = function <T>() {
    let resolve!: (value: T | PromiseLike<T>) => void;
    let reject!: (reason?: any) => void;
    const promise = new Promise<T>((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}
