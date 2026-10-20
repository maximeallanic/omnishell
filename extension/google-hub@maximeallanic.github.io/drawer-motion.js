// M3E motion of the Gemini drawer, after the modal navigation drawer of Jetpack Compose (NavigationDrawer.kt): opens
// on the DefaultSpatial spring, closes on FastEffects (no bounce); the overshoot of the opening stretches the drawer
// from the screen edge (horizontalScaleUp) instead of pulling it away from the edge.
// Interruptible: opening while it closes (or the reverse) starts from the current position and velocity.
// Mechanism: a driver effect "google-hub-drawer" on the window actor; its "position" (px) is driven by a spring of the
// embedded M3E toolkit (m3e/) and turned into translation_x + scale_x (logic.js, drawerGeometry). The effect is removed
// and the actor reset to translation 0 / scale 1 at the end of every movement.
import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import St from 'gi://St';

import {animate} from './m3e/animate.js';
import {drawerGeometry, drawerPosition} from './logic.js';

const EFFECT_NAME = 'google-hub-drawer';
const PROP = `@effects.${EFFECT_NAME}.position`;

const DrawerEffect = GObject.registerClass({GTypeName: 'GoogleHubDrawerEffect'},
class DrawerEffect extends Clutter.Effect {
    _init(actor) {
        super._init();
        this._actor = actor;
        this.requestedWidth = 0; // frame width asked with move_resize_frame, before the client applies it
    }

    get width() {
        return Math.max(1, this.requestedWidth || this._actor.width);
    }

    get position() {
        return drawerPosition(this._actor.translation_x, this._actor.scale_x, this.width);
    }

    set position(v) {
        const {translation, scale} = drawerGeometry(v, this.width);
        this._actor.translation_x = translation;
        this._actor.scale_x = scale;
    }
});

function effectOf(actor) {
    let e = actor.get_effect(EFFECT_NAME);
    if (!e) {
        actor.set_pivot_point(1, 0.5); // right edge: the stretch starts from the screen edge
        e = new DrawerEffect(actor);
        actor.add_effect_with_name(EFFECT_NAME, e);
    }
    return e;
}

function removeEffect(actor) {
    actor.remove_effect_by_name(EFFECT_NAME);
    actor.translation_x = 0;
    actor.scale_x = 1;
    actor.set_pivot_point(0, 0);
}

// open: true (towards the open position) or false (towards the edge); onDone() on arrival only.
// width: drawer width when it was just requested (otherwise the actor's).
export function slideDrawer(actor, open, onDone = () => {}, width = 0) {
    const e = effectOf(actor);
    if (width)
        e.requestedWidth = width;
    const target = open ? e.width : 0;
    if (!St.Settings.get().enable_animations || !actor.mapped) {
        e.position = target;
        removeEffect(actor);
        onDone();
        return null;
    }
    return animate(actor, {[PROP]: target}, {
        spring: open ? 'DefaultSpatial' : 'FastEffects',
        onDone: () => {
            removeEffect(actor);
            onDone();
        },
    });
}

// True while a slide of the drawer is running (effect in place).
export function drawerMoving(actor) {
    return Boolean(actor?.get_effect(EFFECT_NAME));
}

// Places the drawer at once (hidden at the edge, or open) without animation, keeping the effect for a slide.
export function placeDrawer(actor, open, width = 0) {
    const e = effectOf(actor);
    if (width)
        e.requestedWidth = width;
    e.position = open ? e.width : 0;
}

export function stopDrawer(actor) {
    if (actor)
        removeEffect(actor);
}
