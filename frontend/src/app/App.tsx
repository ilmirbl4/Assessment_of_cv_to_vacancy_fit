import { useState } from 'react';
import { RouterProvider } from 'react-router';
import { createAppRouter } from './router';

/** Корневой компонент: создаёт роутер один раз. */
export function App() {
  const [router] = useState(createAppRouter);
  return <RouterProvider router={router} />;
}
