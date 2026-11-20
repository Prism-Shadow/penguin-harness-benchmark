import type { IServer } from '@stoplight/types';

import { getServersToDisplay, getServerUrlWithVariableValues, resolveUrl } from '../IServer';

describe('IServer', () => {
  describe('resolveUrl(getServerUrlWithVariableValues())', () => {
    it('should handle invalid server URLs', () => {
      const server: IServer = {
        id: 'http-server-https://[env].stoplight.io/v1',
        url: 'https://[env].stoplight.io/v1',
      };

      expect(resolveUrl(getServerUrlWithVariableValues(server, {}))).toBeNull();
    });
  });

  describe('getServersToDisplay', () => {
    it('should filter out server objects containing invalid URLs', () => {
      const servers: IServer[] = [
        {
          id: 'http-server-https://[env].stoplight.io/v1',
          url: 'https://[env].stoplight.io/v1',
        },
        {
          id: 'http-server-https://stoplight.io/v1',
          url: 'https://stoplight.io/v1',
        },
      ];

      expect(getServersToDisplay(servers)).toStrictEqual([
        { id: 'http-server-https://stoplight.io/v1', description: 'Server 2', url: 'https://stoplight.io/v1' },
      ]);
    });
  });
});
