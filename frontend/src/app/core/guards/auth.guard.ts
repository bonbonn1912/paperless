import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { map } from 'rxjs';

export const authGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAuthenticated()) {
    return true;
  }

  return authService.checkAuth().pipe(
    map((res) => {
      if (res && res.is_authenticated) {
        return true;
      }
      return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
    })
  );
};
