// Promise that resolves to null as soon as the cancellable is cancelled (without waiting for the D-Bus reply):
// the Shell always writes the result of a search, even a cancelled one, into the current search.
export function untilCancelled(promise, cancellable) {
    if (!cancellable)
        return promise;
    if (cancellable.is_cancelled())
        return Promise.resolve(null);
    return new Promise((resolve, reject) => {
        const id = cancellable.connect(() => resolve(null));
        promise.then(resolve, reject).finally(() => cancellable.disconnect(id));
    });
}
